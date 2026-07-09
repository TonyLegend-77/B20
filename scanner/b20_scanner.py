#!/usr/bin/env python3
"""
B20 Pulse Scanner
Real-time / historical scanner for new B20 tokens on Base.

Detects B20Created events from the official B20Factory precompile.
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
from typing import Any, List, Optional

from web3 import Web3
from web3.contract import Contract
from eth_hash.auto import keccak

# ==================== CONFIG ====================
B20_FACTORY = "0xB20f000000000000000000000000000000000000"
BASE_CHAIN_ID = 8453
BASESCAN_TOKEN = "https://basescan.org/token/"
UNISWAP_BASE = "https://app.uniswap.org/swap?chain=base"

# B20Created event signature
EVENT_SIGNATURE = "B20Created(address,uint8,string,string,uint8,bytes)"
EVENT_TOPIC = "0x" + keccak(EVENT_SIGNATURE.encode()).hex()

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

def decode_b20_created_log(log: dict, w3: Web3) -> Optional[B20Token]:
    try:
        topics = log["topics"]
        data = bytes.fromhex(log["data"].removeprefix("0x"))

        # topics[0] = event signature
        # topics[1] = token (indexed)
        # topics[2] = variant (indexed uint8)

        token_address = "0x" + topics[1].hex()[-40:]
        variant_raw = int.from_bytes(topics[2], "big")
        variant = "ASSET" if variant_raw == 0 else "STABLECOIN"

        # data layout: name (string), symbol (string), decimals (uint8), variantEventParams (bytes)
        # We use a simple decoder for the main fields
        offset = 0

        # name
        name_len = int.from_bytes(data[offset+32:offset+64], "big")
        name = data[offset+64:offset+64+name_len].decode("utf-8", errors="ignore")
        offset += 64 + ((name_len + 31) // 32) * 32

        # symbol
        symbol_len = int.from_bytes(data[offset+32:offset+64], "big")
        symbol = data[offset+64:offset+64+symbol_len].decode("utf-8", errors="ignore")
        offset += 64 + ((symbol_len + 31) // 32) * 32

        # decimals
        decimals = int.from_bytes(data[offset:offset+32], "big")

        block = log["blockNumber"]
        tx_hash = log["transactionHash"].hex() if hasattr(log["transactionHash"], "hex") else log["transactionHash"]

        # Timestamp (we'll fetch block timestamp separately for accuracy in live mode)
        ts = datetime.now(timezone.utc).isoformat()

        is_meme, meme_score = classify_meme(name, symbol)

        return B20Token(
            block_number=block,
            timestamp=ts,
            tx_hash=tx_hash,
            token_address=token_address,
            variant=variant,
            name=name,
            symbol=symbol,
            decimals=decimals,
            is_likely_meme=is_meme,
            meme_score=meme_score,
            basescan_url=f"{BASESCAN_TOKEN}{token_address}",
            uniswap_url=f"{UNISWAP_BASE}&outputCurrency={token_address}"
        )
    except Exception as e:
        print(f"Failed to decode log: {e}")
        return None

def classify_meme(name: str, symbol: str) -> tuple[bool, int]:
    text = (name + " " + symbol).lower()
    score = 0
    for kw in MEME_KEYWORDS:
        if kw in text:
            score += 15
    score = min(score, 100)
    is_meme = score >= 30 or any(kw in text for kw in ["pepe", "doge", "420", "b20", "jesse", "base"])
    return is_meme, score

def scan_historical(w3: Web3, from_block: int, to_block: int) -> List[B20Token]:
    print(f"Scanning blocks {from_block} → {to_block} ...")
    logs = w3.eth.get_logs({
        "fromBlock": from_block,
        "toBlock": to_block,
        "address": B20_FACTORY,
        "topics": [EVENT_TOPIC]
    })

    tokens: List[B20Token] = []
    for log in logs:
        token = decode_b20_created_log(log, w3)
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

    # JSON
    json_path = output_dir / "b20_tokens.json"
    with open(json_path, "w") as f:
        json.dump([asdict(t) for t in tokens], f, indent=2)
    print(f"Saved JSON → {json_path}")

    # CSV
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

            # Print summary of top memes
            memes = sorted([t for t in tokens if t.is_likely_meme], key=lambda x: x.meme_score, reverse=True)[:10]
            if memes:
                print("\n=== Top Likely Memes ===")
                for t in memes:
                    print(f"{t.symbol:12} | Score: {t.meme_score:3} | {t.name}")

if __name__ == "__main__":
    main()