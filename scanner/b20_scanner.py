# ... (keep all imports and config the same) ...

# Add these improvements:

def scan_historical(w3: Web3, from_block: int, to_block: int, batch_size: int = 50) -> List[B20Token]:
    """
    Scan a block range for successful createB20 calls.
    Uses batching to reduce RPC load.
    """
    print(f"Scanning blocks {from_block} → {to_block} for createB20 calls...")
    tokens: List[B20Token] = []
    
    # Process in batches
    current = from_block
    while current <= to_block:
        batch_end = min(current + batch_size - 1, to_block)
        
        for block_num in range(current, batch_end + 1):
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
                    continue

                token = decode_b20_creation_tx(dict(tx), dict(receipt), w3, block.timestamp)
                if token:
                    tokens.append(token)
                    print(f"  Found: {token.name} ({token.symbol}) at {token.token_address}")
        
        # Progress indicator
        if batch_end < to_block:
            print(f"  Progress: {batch_end}/{to_block} ({len(tokens)} tokens found)")
        
        current = batch_end + 1

    return tokens
