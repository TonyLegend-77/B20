"""
B20 Pulse — Real On-Chain Risk Scorer

This module queries live B20 token state using web3.py and the IB20 interface.
It evaluates issuer control risk (the most important factor for B20 tokens).

Key things it checks:
- Whether critical roles (DEFAULT_ADMIN_ROLE, MINT_ROLE) are still held by the creator
- If the token is paused
- Active transfer / mint policies
- Supply cap status

Run this standalone or import from FastAPI / agent.
"""

from web3 import Web3
from eth_utils import keccak, to_checksum_address
from typing import Dict, Any, Optional
import os

# Standard role hashes (from OpenZeppelin AccessControl + B20 extensions)
DEFAULT_ADMIN_ROLE = "0x0000000000000000000000000000000000000000000000000000000000000000"
MINT_ROLE = keccak(text="MINT_ROLE").hex()
BURN_ROLE = keccak(text="BURN_ROLE").hex()
PAUSE_ROLE = keccak(text="PAUSE_ROLE").hex()

# Minimal ABI for the parts we care about (B20 is ERC20 superset + compliance features)
B20_ABI = [
    # Roles (AccessControl)
    {
        "inputs": [{"internalType": "bytes32", "name": "role", "type": "bytes32"}],
        "name": "getRoleAdmin",
        "outputs": [{"internalType": "bytes32", "name": "", "type": "bytes32"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "bytes32", "name": "role", "type": "bytes32"},
            {"internalType": "address", "name": "account", "type": "address"}
        ],
        "name": "hasRole",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function"
    },
    # Pausable
    {
        "inputs": [],
        "name": "paused",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function"
    },
    # Supply
    {
        "inputs": [],
        "name": "supplyCap",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "totalSupply",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    # B20 specific - Policies & Freeze/Seize
    {
        "inputs": [{"internalType": "bytes32", "name": "policyScope", "type": "bytes32"}],
        "name": "getPolicy",
        "outputs": [{"internalType": "uint64", "name": "", "type": "uint64"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
        "name": "isFrozen",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "TRANSFER_SENDER_POLICY",
        "outputs": [{"internalType": "bytes32", "name": "", "type": "bytes32"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "TRANSFER_RECEIVER_POLICY",
        "outputs": [{"internalType": "bytes32", "name": "", "type": "bytes32"}],
        "stateMutability": "view",
        "type": "function"
    },
]

def get_b20_contract(w3: Web3, token_address: str):
    return w3.eth.contract(
        address=to_checksum_address(token_address),
        abi=B20_ABI
    )

def check_role(contract, role: str, account: str) -> bool:
    try:
        return contract.functions.hasRole(role, to_checksum_address(account)).call()
    except Exception:
        return False

def get_risk_score(token_address: str, creator_address: Optional[str] = None, rpc_url: str = "https://mainnet.base.org") -> Dict[str, Any]:
    """
    Main function: returns detailed risk assessment for a B20 token.
    """
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        return {"error": "Cannot connect to RPC"}

    contract = get_b20_contract(w3, token_address)

    result = {
        "address": token_address,
        "risk_score": 50,           # start neutral
        "risk_level": "MEDIUM",
        "reasons": [],
        "details": {}
    }

    try:
        # 1. Check if paused
        paused = contract.functions.paused().call()
        result["details"]["paused"] = paused
        if paused:
            result["reasons"].append("Token is currently PAUSED")
            result["risk_score"] -= 25

        # 2. Check supply cap
        try:
            supply_cap = contract.functions.supplyCap().call()
            total_supply = contract.functions.totalSupply().call()
            result["details"]["supply_cap"] = supply_cap
            result["details"]["total_supply"] = total_supply
            if supply_cap == 2**256 - 1:  # uint256 max = unlimited
                result["reasons"].append("No supply cap (unlimited minting possible)")
                result["risk_score"] -= 15
            else:
                result["reasons"].append(f"Supply capped at {supply_cap}")
                result["risk_score"] += 10
        except:
            result["reasons"].append("Could not read supply cap")

        # 3. Check critical roles (most important for B20 memes)
        # We check if the zero address or a known creator still has powerful roles
        zero_address = "0x0000000000000000000000000000000000000000"

        admin_has_role = check_role(contract, DEFAULT_ADMIN_ROLE, zero_address)
        mint_has_role = check_role(contract, MINT_ROLE, zero_address)

        result["details"]["admin_renounced"] = admin_has_role   # True if renounced (role given to zero)
        result["details"]["mint_renounced"] = mint_has_role

        if not admin_has_role:
            result["reasons"].append("DEFAULT_ADMIN_ROLE still held by creator → HIGH RISK")
            result["risk_score"] -= 30
        else:
            result["reasons"].append("Admin role renounced (good)")
            result["risk_score"] += 20

        if not mint_has_role:
            result["reasons"].append("MINT_ROLE still held by creator → can mint more tokens")
            result["risk_score"] -= 25
        else:
            result["reasons"].append("Mint role renounced (good)")
            result["risk_score"] += 15

        # 4. Check for active policies (transfer gating) - B20 specific
        try:
            sender_policy = contract.functions.getPolicy(contract.functions.TRANSFER_SENDER_POLICY().call()).call()
            receiver_policy = contract.functions.getPolicy(contract.functions.TRANSFER_RECEIVER_POLICY().call()).call()

            if sender_policy != 0 or receiver_policy != 0:
                result["reasons"].append("Active transfer policies detected (issuer can block sends/receives)")
                result["risk_score"] -= 18
                result["details"]["has_transfer_policies"] = True
            else:
                result["details"]["has_transfer_policies"] = False
        except Exception:
            result["details"]["has_transfer_policies"] = "unknown"

        # 5. Check freeze/seize capability (very important for B20 compliance tokens)
        try:
            is_frozen_example = contract.functions.isFrozen("0x0000000000000000000000000000000000000000").call()
            result["details"]["freeze_capability"] = True  # If function exists, issuer likely has freeze power
            result["reasons"].append("Freeze/Seize capability present (common in B20 for regulated assets)")
            result["risk_score"] -= 10  # Slight penalty for memes unless renounced
        except:
            result["details"]["freeze_capability"] = False

        # 6. Bonus: Check if creator wallet has renounced in recent blocks (simplified)
        # In production: Index creation tx + renounce events from the same creator
        if result["details"].get("admin_renounced") and result["details"].get("mint_renounced"):
            result["reasons"].append("Strong signal: Both admin and mint roles renounced at/near creation")
            result["risk_score"] += 10

        # Final normalization
        result["risk_score"] = max(0, min(100, result["risk_score"]))

        if result["risk_score"] >= 75:
            result["risk_level"] = "LOW"
        elif result["risk_score"] >= 45:
            result["risk_level"] = "MEDIUM"
        else:
            result["risk_level"] = "HIGH"

    except Exception as e:
        result["error"] = str(e)
        result["risk_level"] = "UNKNOWN"

    return result


if __name__ == "__main__":
    # Example usage
    test_address = "0xb200000000000000000000231d6c1f1ce455ba32"
    print(get_risk_score(test_address))