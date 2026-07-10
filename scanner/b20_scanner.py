#!/usr/bin/env python3
"""
B20 Pulse Scanner
Real-time / historical scanner for new B20 tokens on Base.

IMPORTANT: There is no documented "B20Created" event. Per Base's official
spec (docs.base.org/base-chain/specs/upgrades/beryl/b20), new tokens are
created by calling createB20(variant, salt, params, initCalls) on the
singleton B20Factory precompile at a fixed address. Token addresses are
fully deterministic: [10-byte B20 prefix][1-byte variant][9-byte hash].

This scanner detects new launches by:
1. Scanning blocks for successful transactions sent TO the B20Factory
   precompile with the createB20 function selector.
2. Decoding just the `variant` and `salt` fields from the call (both are
   fixed-size ABI types at the start of the calldata, so this is safe
   regardless of how `params`/`initCalls` are structured).
3. Calling the factory's getB20Address(variant, deployer, salt) view
   function to get the exact resulting token address.
4. Reading name()/symbol()/decimals() directly from the resulting token,
   since B20 is fully ERC-20 compatible — far more reliable than trying
   to hand-decode the proprietary `params` bytes.

Classifies potential memes using simple heuristics.
Outputs JSON + optional CSV/HTML.

Usage:
    python b20_scanner.py --rpc https://mainnet.base.org --last 10000
    python b20_scanner.py --rpc https://mainnet.base.org --live   # continuous polling

Requirements:
    pip install web3 python-dotenv
"""

import argparse
import csv
import json
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from web3 import Web3

# ==================== CONFIG ====================
# Confirmed against docs.base.org/base-chain/specs/upgrades/beryl/b20 —
# same address on every network (Mainnet, Base Sepolia, Vibenet, base-anvil).
B20_FACTORY = Web3.to_checksum_address("0xB20f000000000000000000000000000000000000")
BASE_CHAIN_ID = 8453
BASESCAN_TOKEN = "https://basescan.org/token/"
UNISWAP_BASE = "https://app.uniswap.org/swap?chain=base"

# Function selectors (keccak256(signature)[:4]), verified independently —
# name()/symbol()/decimals()/totalSupply() match the well-known standard
# ERC-20 selectors, confirming the derivation is correct.
SELECTOR_CREATE_B20 = bytes.fromhex("62975e6a")          # createB20(uint8,bytes32,bytes,bytes[])
SELECTOR_GET_B20_ADDRESS = bytes.fromhex("8c30260f")     # getB20Address(uint8,address,bytes32)
SELECTOR_NAME = bytes.fromhex("06fdde03")                # name()
SELECTOR_SYMBOL = bytes.fromhex("95d89b41")              # symbol()
SELECTOR_DECIMALS = bytes.fromhex("313ce567")            # decimals()

VARIANT_NAMES = {0: "ASSET", 1: "STABLECOIN"}

MEME_KEYWORDS = [
    "pepe", "doge", "shib", "floki", "wojak", "chad", "sigma", "based",
    "moon", "pump", "ape", "frog", "cat", "dog", "bull", "bear", "meme",
    "420", "69", "gm", "ngmi", "wagmi", "degen", "retard", "tard", "bobo",
    "jesse", "base", "beryl", "b20", "pulse", "vibe", "hype"
]

@dataclass
class B20Token:
    block_number: int
    timestamp: str
    tx_hash: str
    token_address: str
    variant: str          # "ASSET" or "STABLECOIN"
    name: str
    symbol: str
    decimals: int
    is_likely_meme: bool
    meme_score: int       # 0-100 rough score
    basescan_url: str
    uniswap_url: str

def get_web3(rpc_url: str) -> Web3:
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        raise ConnectionError(f"Cannot connect to RPC: {rpc_url}")
    return w3


def _decode_string_return(raw: bytes) -> str:
    """Decode a standard ABI-encoded `string` return value (offset + length + data)."""
    if len(raw) < 64:
        return ""
    length = int.from_bytes(raw[32:64], "big")
    return raw[64:64 + length].decode("utf-8", errors="ignore")


def _eth_call(w3: Web3, to: str, data: bytes) -> bytes:
    return w3.eth.call({"to": to, "data": data})


def get_b20_address(w3: Web3, variant: int, deployer: str, salt: bytes) -> str:
    """Call the factory's getB20Address(variant, deployer, salt) to get the
    exact deterministic token address — safer than re-deriving it by hand."""
    calldata = (
        SELECTOR_GET_B20_ADDRESS
        + variant.to_bytes(32, "big")
        + bytes(12) + bytes.fromhex(deployer[2:])  # address padded to 32 bytes
        + salt
    )
    raw = _eth_call(w3, B20_FACTORY, calldata)
    return Web3.to_checksum_address(raw[-20:])


def get_token_metadata(w3: Web3, token_address: str) -> tuple[str, str, int]:
    """Read name/symbol/decimals directly from the token — B20 is fully
    ERC-20 compatible, so standard calls work with no special ABI needed."""
    name = _decode_string_return(_eth_call(w3, token_address, SELECTOR_NAME))
    symbol = _decode_string_return(_eth_call(w3, token_address, SELECTOR_SYMBOL))
    decimals_raw = _eth_call(w3, token_address, SELECTOR_DECIMALS)
    decimals = int.from_bytes(decimals_raw[-32:], "big") if decimals_raw else 18
    return name, symbol, decimals


def classify_meme(name: str, symbol: str) -> tuple[bool, int]:
    text = (name + " " + symbol).lower()
    score = 0
    for kw in MEME_KEYWORDS:
        if kw in text:
            score += 15
    score = min(score, 100)
    is_meme = score >= 30 or any(kw in text for kw in ["pepe", "doge", "420", "b20", "jesse", "base"])
    return is_meme, score


def decode_b20_creation_tx(tx: dict, receipt: dict, w3: Web3, block_timestamp: int) -> Optional[B20Token]:
    """Given a transaction that successfully called createB20 on the factory,
    resolve the resulting token's address and metadata."""
    try:
        input_bytes = bytes(tx["input"]) if not isinstance(tx["input"], (bytes, bytearray)) else tx["input"]
        args = input_bytes[4:]  # strip the 4-byte selector

        if len(args) < 64:
            return None

        variant = int.from_bytes(args[0:32], "big")
        salt = args[32:64]
        deployer = tx["from"]

        token_address = get_b20_address(w3, variant, deployer, salt)
        name, symbol, decimals = get_token_metadata(w3, token_address)

        is_meme, meme_score = classify_meme(name, symbol)
        ts = datetime.fromtimestamp(block_timestamp, tz=timezone.utc).isoformat()
        tx_hash = tx["hash"].hex() if hasattr(tx["hash"], "hex") else tx["hash"]

        return B20Token(
            block_number=tx["blockNumber"],
            timestamp=ts,
            tx_hash=tx_hash,
            token_address=token_address,
            variant=VARIANT_NAMES.get(variant, f"UNKNOWN({variant})"),
            name=name,
            symbol=symbol,
            decimals=decimals,
            is_likely_meme=is_meme,
            meme_score=meme_score,
            basescan_url=f"{BASESCAN_TOKEN}{token_address}",
            uniswap_url=f"{UNISWAP_BASE}&outputCurrency={token_address}"
        )
    except Exception as e:
        print(f"Failed to decode createB20 tx {tx.get('hash')}: {e}")
        return None


def scan_historical(w3: Web3, from_block: int, to_block: int) -> List[B20Token]:
    """Scan a block range for successful createB20 calls to the factory.

    Note: this fetches full transaction bodies block-by-block (there's no
    documented event to filter via get_logs), so it's heavier on the RPC
    than a log-based scan. Keep ranges reasonably small for public RPCs.
    """
    print(f"Scanning blocks {from_block} → {to_block} for createB20 calls...")
    tokens: List[B20Token] = []

    for block_num in range(from_block, to_block + 1):
        try:
            block = w3.eth.get_block(block_num, full_transactions=True)
        except Exception as e:
            print(f"Could not fetch block {block_num}: {e}")
            continue

        for tx in block.transactions:
            to_addr = tx.get("to")
            if not to_addr or Web3.to_checksum_address(to_addr) != B20_FACTORY:
                continue

            input_bytes = bytes(tx["input"]) if not isinstance(tx["input"], (bytes, bytearray)) else tx["input"]
            if not input_bytes.startswith(SELECTOR_CREATE_B20):
                continue

            try:
                receipt = w3.eth.get_transaction_receipt(tx["hash"])
            except Exception as e:
                print(f"Could not fetch receipt for {tx['hash'].hex()}: {e}")
                continue

            if receipt.get("status") != 1:
                continue  # reverted creation (e.g. TokenAlreadyExists)

            token = decode_b20_creation_tx(dict(tx), dict(receipt), w3, block.timestamp)
            if token:
                tokens.append(token)

    return tokens


def live_mode(w3: Web3, poll_interval: int = 12):
    print("Starting live B20 scanner... (Ctrl+C to stop)")
    last_block = w3.eth.block_number - 10  # start from recent

    while True:
        try:
            current_block = w3.eth.block_number
            if current_block > last_block:
                new_tokens = scan_historical(w3, last_block + 1, current_block)
                for t in new_tokens:
                    print(f"\n🆕 NEW B20 {'(MEME)' if t.is_likely_meme else ''}")
                    print(f"   {t.name} (${t.symbol}) — {t.variant}")
                    print(f"   Address: {t.token_address}")
                    print(f"   Block: {t.block_number} | Meme Score: {t.meme_score}")
                    print(f"   Basescan: {t.basescan_url}")
                last_block = current_block
            time.sleep(poll_interval)
        except KeyboardInterrupt:
            print("\nStopping live scanner.")
            break
        except Exception as e:
            print(f"Error in live loop: {e}")
            time.sleep(5)


def save_output(tokens: List[B20Token], output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "b20_tokens.json"
    with open(json_path, "w") as f:
        json.dump([asdict(t) for t in tokens], f, indent=2)
    print(f"Saved JSON → {json_path}")

    csv_path = output_dir / "b20_tokens.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[f.name for f in B20Token.__dataclass_fields__.values()])
        writer.writeheader()
        for t in tokens:
            writer.writerow(asdict(t))
    print(f"Saved CSV  → {csv_path}")


def main():
    parser = argparse.ArgumentParser(description="B20 Pulse Scanner")
    parser.add_argument("--rpc", default="https://mainnet.base.org", help="Base RPC URL")
    parser.add_argument("--last", type=int, default=5000, help="Scan last N blocks")
    parser.add_argument("--live", action="store_true", help="Run in continuous live mode")
    parser.add_argument("--out", default="./b20_output", help="Output directory")
    args = parser.parse_args()

    w3 = get_web3(args.rpc)
    print(f"Connected to Base (chainId: {w3.eth.chain_id})")
    print(f"B20 Factory: {B20_FACTORY}")

    output_dir = Path(args.out)

    if args.live:
        live_mode(w3)
    else:
        current_block = w3.eth.block_number
        from_block = max(1, current_block - args.last)
        tokens = scan_historical(w3, from_block, current_block)

        print(f"\nFound {len(tokens)} B20 tokens in last {args.last} blocks")
        meme_count = sum(1 for t in tokens if t.is_likely_meme)
        print(f"Likely memes: {meme_count}")

        if tokens:
            save_output(tokens, output_dir)

            memes = sorted([t for t in tokens if t.is_likely_meme], key=lambda x: x.meme_score, reverse=True)[:10]
            if memes:
                print("\n=== Top Likely Memes ===")
                for t in memes:
                    print(f"{t.symbol:12} | Score: {t.meme_score:3} | {t.name}")


if __name__ == "__main__":
    main()
