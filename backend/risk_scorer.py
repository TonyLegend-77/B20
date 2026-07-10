"""
B20 Pulse — Real On-Chain Risk Scorer

Queries live B20 token state using web3.py against the real IB20 interface.
"""

from web3 import Web3
from eth_utils import to_checksum_address
from typing import Dict, Any, Optional

B20_ABI = [
    {"inputs": [], "name": "DEFAULT_ADMIN_ROLE", "outputs": [{"internalType": "bytes32", "name": "", "type": "bytes32"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "MINT_ROLE", "outputs": [{"internalType": "bytes32", "name": "", "type": "bytes32"}], "stateMutability": "view", "type": "function"},
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
    {"inputs": [], "name": "pausedFeatures", "outputs": [{"internalType": "uint8[]", "name": "", "type": "uint8[]"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "supplyCap", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "totalSupply", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {
        "inputs": [{"internalType": "bytes32", "name": "policyScope", "type": "bytes32"}],
        "name": "policyId",
        "outputs": [{"internalType": "uint64", "name": "", "type": "uint64"}],
        "stateMutability": "view",
        "type": "function"
    },
    {"inputs": [], "name": "TRANSFER_SENDER_POLICY", "outputs": [{"internalType": "bytes32", "name": "", "type": "bytes32"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "TRANSFER_RECEIVER_POLICY", "outputs": [{"internalType": "bytes32", "name": "", "type": "bytes32"}], "stateMutability": "view", "type": "function"},
]

PAUSABLE_FEATURE_NAMES = {0: "TRANSFER", 1: "MINT", 2: "BURN"}
UNCAPPED_SENTINEL = (2 ** 128) - 1


def _get_b20_contract(w3: Web3, token_address: str):
    """Get B20 contract instance with validation."""
    try:
        checksum_addr = to_checksum_address(token_address)
    except Exception as e:
        raise ValueError(f"Invalid address format: {token_address}") from e
    
    return w3.eth.contract(address=checksum_addr, abi=B20_ABI)


def _check_role(contract, role: bytes, account: str) -> Optional[bool]:
    """Returns True/False, or None if the call failed."""
    try:
        return contract.caller.hasRole(role, to_checksum_address(account))
    except Exception:
        return None


def get_light_state(token_address: str, rpc_url: str = "https://mainnet.base.org") -> Dict[str, Any]:
    """
    Lightweight read for quick 'is it paused / what's the supply' questions.
    """
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        return {"error": "Cannot connect to RPC", "rpc_url": rpc_url}

    try:
        contract = _get_b20_contract(w3, token_address)
    except ValueError as e:
        return {"error": str(e)}

    try:
        paused_features = contract.caller.pausedFeatures()
        supply_cap = contract.caller.supplyCap()
        total_supply = contract.caller.totalSupply()
        
        return {
            "address": token_address,
            "paused_features": [PAUSABLE_FEATURE_NAMES.get(f, str(f)) for f in paused_features],
            "supply_cap": str(supply_cap),
            "total_supply": str(total_supply),
            "is_capped": supply_cap != UNCAPPED_SENTINEL,
            "rpc_connected": True,
        }
    except Exception as e:
        return {
            "error": f"Failed to read token state: {str(e)}",
            "address": token_address,
            "note": "This address may not be a valid B20 token or may not be initialized on this network."
        }


def get_risk_score(
    token_address: str,
    creator_address: Optional[str] = None,
    rpc_url: str = "https://mainnet.base.org"
) -> Dict[str, Any]:
    """
    Main function: returns detailed risk assessment for a B20 token.
    """
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        return {
            "error": "Cannot connect to RPC",
            "address": token_address,
            "risk_score": 0,
            "risk_level": "UNKNOWN",
            "reasons": ["RPC connection failed"],
            "details": {"rpc_url": rpc_url}
        }

    try:
        contract = _get_b20_contract(w3, token_address)
    except ValueError as e:
        return {
            "error": str(e),
            "address": token_address,
            "risk_score": 0,
            "risk_level": "INVALID",
            "reasons": ["Invalid address format"],
            "details": {}
        }

    result = {
        "address": token_address,
        "risk_score": 50,
        "risk_level": "MEDIUM",
        "reasons": [],
        "details": {}
    }

    try:
        # 1. Pause state
        paused_features = contract.caller.pausedFeatures()
        paused_names = [PAUSABLE_FEATURE_NAMES.get(f, str(f)) for f in paused_features]
        result["details"]["paused_features"] = paused_names
        
        if 0 in paused_features:
            result["reasons"].append("Transfers are currently PAUSED")
            result["risk_score"] -= 25
        if 1 in paused_features:
            result["reasons"].append("Minting is currently paused")

        # 2. Supply cap
        supply_cap = contract.caller.supplyCap()
        total_supply = contract.caller.totalSupply()
        result["details"]["supply_cap"] = str(supply_cap)
        result["details"]["total_supply"] = str(total_supply)
        
        if supply_cap == UNCAPPED_SENTINEL:
            result["reasons"].append("No supply cap set (unlimited minting possible)")
            result["risk_score"] -= 15
        else:
            result["reasons"].append(f"Supply capped at {supply_cap}")
            result["risk_score"] += 10

        # 3. Role renunciation
        admin_role = contract.caller.DEFAULT_ADMIN_ROLE()
        mint_role = contract.caller.MINT_ROLE()

        if creator_address:
            creator_has_admin = _check_role(contract, admin_role, creator_address)
            creator_has_mint = _check_role(contract, mint_role, creator_address)

            result["details"]["admin_renounced"] = (creator_has_admin is False)
            result["details"]["mint_renounced"] = (creator_has_mint is False)
            result["details"]["creator_address"] = creator_address

            if creator_has_admin is True:
                result["reasons"].append("DEFAULT_ADMIN_ROLE still held by creator → HIGH RISK")
                result["risk_score"] -= 30
            elif creator_has_admin is False:
                result["reasons"].append("Admin role renounced by creator (good)")
                result["risk_score"] += 20
            else:
                result["reasons"].append("Could not verify admin role status (RPC error?)")

            if creator_has_mint is True:
                result["reasons"].append("MINT_ROLE still held by creator → can mint more tokens")
                result["risk_score"] -= 25
            elif creator_has_mint is False:
                result["reasons"].append("Mint role renounced by creator (good)")
                result["risk_score"] += 15
            else:
                result["reasons"].append("Could not verify mint role status (RPC error?)")

            if result["details"].get("admin_renounced") and result["details"].get("mint_renounced"):
                result["reasons"].append("Strong signal: creator holds neither admin nor mint role")
                result["risk_score"] += 10
        else:
            result["details"]["admin_renounced"] = "unknown"
            result["details"]["mint_renounced"] = "unknown"
            result["reasons"].append("Creator address not available — cannot verify role renunciation")

        # 4. Transfer policies
        try:
            sender_scope = contract.caller.TRANSFER_SENDER_POLICY()
            receiver_scope = contract.caller.TRANSFER_RECEIVER_POLICY()
            sender_policy = contract.caller.policyId(sender_scope)
            receiver_policy = contract.caller.policyId(receiver_scope)

            has_policies = sender_policy != 0 or receiver_policy != 0
            result["details"]["has_transfer_policies"] = has_policies
            result["details"]["sender_policy_id"] = sender_policy
            result["details"]["receiver_policy_id"] = receiver_policy
            
            if has_policies:
                result["reasons"].append("Active transfer policy configured (issuer can gate sends/receives)")
                result["risk_score"] -= 18
        except Exception:
            result["details"]["has_transfer_policies"] = "unknown"

        # 5. Freeze/seize capability note
        result["details"]["freeze_seize_capability"] = "inherent to B20 standard"

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
        result["reasons"].append(f"Analysis error: {str(e)}")

    return result


if __name__ == "__main__":
    test_address = "0xb200000000000000000000231d6c1f1ce455ba32"
    print("Light state:")
    print(get_light_state(test_address))
    print("\nRisk score:")
    print(get_risk_score(test_address))
