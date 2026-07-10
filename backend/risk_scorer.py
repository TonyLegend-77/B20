"""
B20 Pulse — Real On-Chain Risk Scorer

Queries live B20 token state using web3.py against the real IB20 interface
(docs.base.org/base-chain/specs/upgrades/beryl/b20, ABI confirmed against
github.com/base/base-std/blob/main/src/interfaces/IB20.sol).

Important B20-specific behavior this module relies on:
- Pause state is granular (TRANSFER/MINT/BURN). There is NO niladic
  `paused()` — only `pausedFeatures()` / `isPaused(feature)`.
- Renunciation removes DEFAULT_ADMIN_ROLE / MINT_ROLE outright via
  `renounceLastAdmin()` (or by never granting it). It is NEVER reassigned
  to address(0), unlike the common OZ AccessControl pattern. The only
  reliable way to check "is this renounced" is `hasRole(role, <the address
  that used to hold it>)` — so renunciation checks require a known creator
  address, not the zero address.
- Role constants (MINT_ROLE, BURN_BLOCKED_ROLE, etc.) are read live from the
  token via their getter functions rather than recomputed locally, since
  B20Constants.sol is the only authority for their actual values.
- Scopes are read via `policyId(scope)`, not `getPolicy(scope)`.
- The "uncapped" supply sentinel is `type(uint128).max`, not
  `type(uint256).max`.

Run this standalone or import from FastAPI / agent.
"""

from web3 import Web3
from eth_utils import to_checksum_address
from typing import Dict, Any, Optional

# Minimal ABI for the parts we care about, matching IB20.sol exactly.
B20_ABI = [
    # Role constant getters (IB20.sol "ROLE CONSTANTS") — call these instead
    # of assuming a naive keccak256(name) hash.
    {"inputs": [], "name": "DEFAULT_ADMIN_ROLE", "outputs": [{"internalType": "bytes32", "name": "", "type": "bytes32"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "MINT_ROLE", "outputs": [{"internalType": "bytes32", "name": "", "type": "bytes32"}], "stateMutability": "view", "type": "function"},
    # AccessControl
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
    # Pause — granular. No niladic paused().
    {"inputs": [], "name": "pausedFeatures", "outputs": [{"internalType": "uint8[]", "name": "", "type": "uint8[]"}], "stateMutability": "view", "type": "function"},
    # Supply
    {"inputs": [], "name": "supplyCap", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "totalSupply", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    # Policy — scopes are read via policyId(scope), NOT getPolicy(scope).
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

# PausableFeature enum order per IB20.sol: TRANSFER=0, MINT=1, BURN=2.
PAUSABLE_FEATURE_NAMES = {0: "TRANSFER", 1: "MINT", 2: "BURN"}

# Per spec: the sentinel meaning "no cap" is type(uint128).max, NOT
# type(uint256).max — supplyCap can never exceed uint128 max in the first place.
UNCAPPED_SENTINEL = (2 ** 128) - 1


def get_b20_contract(w3: Web3, token_address: str):
    return w3.eth.contract(
        address=to_checksum_address(token_address),
        abi=B20_ABI
    )


def check_role(contract, role: bytes, account: str) -> Optional[bool]:
    """Returns True/False for a real answer, or None if the call itself
    failed (so callers can tell "confirmed no" apart from "couldn't check")."""
    try:
        return contract.functions.hasRole(role, to_checksum_address(account)).call()
    except Exception:
        return None


def get_light_state(token_address: str, rpc_url: str = "https://mainnet.base.org") -> Dict[str, Any]:
    """Lightweight read for quick "is it paused / what's the supply" questions.
    No role/renunciation check here — that requires a creator address, see
    get_risk_score. Shared by the FastAPI /state route and the Gemini agent's
    get_token_live_state tool so there's one source of truth for the ABI.
    """
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    contract = get_b20_contract(w3, token_address)
    try:
        paused_features = contract.functions.pausedFeatures().call()
        return {
            "paused_features": [PAUSABLE_FEATURE_NAMES.get(f, str(f)) for f in paused_features],
            "supply_cap": contract.functions.supplyCap().call(),
            "total_supply": contract.functions.totalSupply().call(),
        }
    except Exception as e:
        return {"error": str(e)}


def get_risk_score(token_address: str, creator_address: Optional[str] = None, rpc_url: str = "https://mainnet.base.org") -> Dict[str, Any]:
    """
    Main function: returns detailed risk assessment for a B20 token.

    creator_address, when known (e.g. resolved from the scanner's recorded
    deployer for this token), lets us actually check whether admin/mint
    roles have been renounced. Without it, renunciation is reported as
    unknown rather than guessed — B20 has no role-enumeration extension, so
    there is no way to check "does anyone hold this role" without a specific
    address to test.
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
        # 1. Pause state (granular)
        paused_features = contract.functions.pausedFeatures().call()
        paused_names = [PAUSABLE_FEATURE_NAMES.get(f, str(f)) for f in paused_features]
        result["details"]["paused_features"] = paused_names
        if 0 in paused_features:  # TRANSFER paused
            result["reasons"].append("Transfers are currently PAUSED")
            result["risk_score"] -= 25
        if 1 in paused_features:  # MINT paused
            result["reasons"].append("Minting is currently paused")

        # 2. Check supply cap
        try:
            supply_cap = contract.functions.supplyCap().call()
            total_supply = contract.functions.totalSupply().call()
            result["details"]["supply_cap"] = supply_cap
            result["details"]["total_supply"] = total_supply
            if supply_cap == UNCAPPED_SENTINEL:
                result["reasons"].append("No supply cap (unlimited minting possible)")
                result["risk_score"] -= 15
            else:
                result["reasons"].append(f"Supply capped at {supply_cap}")
                result["risk_score"] += 10
        except Exception:
            result["reasons"].append("Could not read supply cap")

        # 3. Admin / mint role renunciation.
        # B20 removes these roles outright on renunciation rather than
        # reassigning to address(0), so this can only be checked against a
        # known former holder (the creator) — never the zero address.
        admin_role = contract.functions.DEFAULT_ADMIN_ROLE().call()
        mint_role = contract.functions.MINT_ROLE().call()

        if creator_address:
            creator_has_admin = check_role(contract, admin_role, creator_address)
            creator_has_mint = check_role(contract, mint_role, creator_address)

            result["details"]["admin_renounced"] = (creator_has_admin is False)
            result["details"]["mint_renounced"] = (creator_has_mint is False)

            if creator_has_admin is True:
                result["reasons"].append("DEFAULT_ADMIN_ROLE still held by creator → HIGH RISK")
                result["risk_score"] -= 30
            elif creator_has_admin is False:
                result["reasons"].append("Admin role renounced by creator (good)")
                result["risk_score"] += 20
            else:
                result["reasons"].append("Could not verify admin role status")

            if creator_has_mint is True:
                result["reasons"].append("MINT_ROLE still held by creator → can mint more tokens")
                result["risk_score"] -= 25
            elif creator_has_mint is False:
                result["reasons"].append("Mint role renounced by creator (good)")
                result["risk_score"] += 15
            else:
                result["reasons"].append("Could not verify mint role status")

            if result["details"].get("admin_renounced") and result["details"].get("mint_renounced"):
                result["reasons"].append("Strong signal: creator holds neither admin nor mint role")
                result["risk_score"] += 10
        else:
            result["details"]["admin_renounced"] = "unknown"
            result["details"]["mint_renounced"] = "unknown"
            result["reasons"].append("Creator address not available — cannot verify role renunciation")

        # 4. Check for active transfer policy gating (B20 specific)
        try:
            sender_scope = contract.functions.TRANSFER_SENDER_POLICY().call()
            receiver_scope = contract.functions.TRANSFER_RECEIVER_POLICY().call()
            sender_policy = contract.functions.policyId(sender_scope).call()
            receiver_policy = contract.functions.policyId(receiver_scope).call()

            has_policies = sender_policy != 0 or receiver_policy != 0
            result["details"]["has_transfer_policies"] = has_policies
            if has_policies:
                result["reasons"].append("Active transfer policy configured (issuer can gate sends/receives)")
                result["risk_score"] -= 18
        except Exception:
            result["details"]["has_transfer_policies"] = "unknown"

        # 5. Freeze/seize capability is inherent to every B20 token
        # (burnBlocked() gated by BURN_BLOCKED_ROLE) — it's part of the base
        # standard, not something individual tokens opt into, so there's
        # nothing to "detect" here. What actually varies is whether a
        # transfer policy (checked above) is configured, since that's the
        # practical precondition for burnBlocked to matter.
        result["details"]["freeze_seize_capability"] = "inherent to B20 standard (burnBlocked / BURN_BLOCKED_ROLE)"

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
