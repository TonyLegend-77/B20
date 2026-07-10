"""
B20 Pulse FastAPI Backend

Serves:
- Recent B20 tokens (from scanner or cache)
- Detailed on-chain risk analysis for any B20 token
- Simple health check

Run with:
    uvicorn backend.main:app --reload --port 8000
"""

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import json
import threading
import time
from pathlib import Path
from datetime import datetime, timezone

# Import our modules
from .risk_scorer import get_risk_score
from scanner.b20_scanner import get_web3, scan_historical, save_output

# Where the scanner writes its output — resolved relative to this file,
# NOT to whatever directory the process happens to be started from.
SCANNER_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "scanner" / "b20_output"
SCANNER_OUTPUT_PATH = SCANNER_OUTPUT_DIR / "b20_tokens.json"

app = FastAPI(
    title="B20 Pulse API",
    description="Backend for B20 token tracking, risk scoring, and AI agent tools on Base",
    version="0.1.0"
)

# CORS for Mini App / local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _humanize_age(timestamp_str: str) -> str:
    """Convert an ISO timestamp into a short 'Xm ago' / 'Xh ago' string."""
    try:
        ts = datetime.fromisoformat(timestamp_str)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - ts
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return f"{seconds}s ago"
        if seconds < 3600:
            return f"{seconds // 60}m ago"
        if seconds < 86400:
            return f"{seconds // 3600}h ago"
        return f"{seconds // 86400}d ago"
    except Exception:
        return "recently"


def _transform_scanner_token(raw: dict) -> dict:
    """Map the scanner's raw B20Token shape into the TokenResponse shape
    the frontend/API contract expects."""
    return {
        "address": raw.get("token_address", ""),
        "name": raw.get("name", "Unknown"),
        "symbol": raw.get("symbol", "???"),
        "variant": raw.get("variant", "ASSET"),
        "age": _humanize_age(raw.get("timestamp", "")),
        "meme_score": raw.get("meme_score", 0),
        "risk_level": "UNKNOWN",  # run /tokens/{address}/risk for the real read
        "liquidity": None,
    }


def _run_background_scanner(rpc_url: str = "https://mainnet.base.org", catch_up_blocks: int = 5000, poll_interval: int = 15):
    """Runs forever in a background thread: does an initial historical
    catch-up, then polls for new blocks, writing results to SCANNER_OUTPUT_PATH
    so /tokens/recent has real data instead of only ever falling back to mock."""
    try:
        w3 = get_web3(rpc_url)
    except Exception as e:
        print(f"[scanner] Could not connect to RPC, background scanner disabled: {e}")
        return

    print(f"[scanner] Connected to Base (chainId: {w3.eth.chain_id}). Starting background scan.")

    all_tokens = []
    try:
        current_block = w3.eth.block_number
        from_block = max(1, current_block - catch_up_blocks)
        all_tokens = scan_historical(w3, from_block, current_block)
        save_output(all_tokens, SCANNER_OUTPUT_DIR)
        print(f"[scanner] Initial catch-up found {len(all_tokens)} tokens.")
        last_block = current_block
    except Exception as e:
        print(f"[scanner] Initial catch-up failed: {e}")
        last_block = w3.eth.block_number

    while True:
        try:
            current_block = w3.eth.block_number
            if current_block > last_block:
                new_tokens = scan_historical(w3, last_block + 1, current_block)
                if new_tokens:
                    all_tokens = new_tokens + all_tokens  # newest first
                    save_output(all_tokens, SCANNER_OUTPUT_DIR)
                    print(f"[scanner] Found {len(new_tokens)} new token(s) at block {current_block}.")
                last_block = current_block
        except Exception as e:
            print(f"[scanner] Error in poll loop: {e}")
        time.sleep(poll_interval)


@app.on_event("startup")
def start_background_scanner():
    thread = threading.Thread(target=_run_background_scanner, daemon=True)
    thread.start()

class TokenResponse(BaseModel):
    address: str
    name: str
    symbol: str
    variant: str
    age: str
    meme_score: int
    risk_level: str
    liquidity: Optional[str] = None

class RiskAnalysisResponse(BaseModel):
    address: str
    risk_score: int
    risk_level: str
    reasons: List[str]
    details: dict

@app.get("/")
async def root():
    return {"message": "B20 Pulse API is live", "docs": "/docs"}

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.get("/tokens/recent", response_model=List[TokenResponse])
async def get_recent_tokens_route(
    limit: int = Query(20, ge=1, le=100),
    meme_only: bool = Query(False)
):
    """HTTP route wrapper — actual logic lives in get_recent_tokens() below
    so it can be called directly (synchronously) from the Gemini agent too."""
    return get_recent_tokens(limit=limit, meme_only=meme_only)


def get_recent_tokens(limit: int = 20, meme_only: bool = False):
    """
    Returns recent B20 tokens.
    For MVP we read from a JSON file produced by the scanner.
    In production: connect to live scanner or database.

    Plain sync function (not a route) so it can be called directly from
    both the FastAPI route above and the Gemini agent's tool calls.
    """
    output_path = SCANNER_OUTPUT_PATH

    if not output_path.exists():
        # Fallback mock data (shown until the background scanner finds real tokens)
        return [
            {
                "address": "0xb200000000000000000000231d6c1f1ce455ba32",
                "name": "B420",
                "symbol": "B420",
                "variant": "ASSET",
                "age": "2h ago",
                "meme_score": 85,
                "risk_level": "MEDIUM",
                "liquidity": "$12.4k"
            }
        ][:limit]

    with open(output_path) as f:
        raw_tokens = json.load(f)

    tokens = [_transform_scanner_token(t) for t in raw_tokens]

    if meme_only:
        tokens = [t for t in tokens if t.get("meme_score", 0) >= 30]

    return tokens[:limit]

@app.get("/tokens/{address}/risk", response_model=RiskAnalysisResponse)
async def analyze_token_risk(
    address: str,
    rpc: str = Query("https://mainnet.base.org", description="Base RPC URL")
):
    """
    Runs full on-chain risk analysis for a B20 token.
    This is the core intelligence of B20 Pulse.
    """
    result = get_risk_score(address, rpc_url=rpc)
    
    if "error" in result:
        return {
            "address": address,
            "risk_score": 0,
            "risk_level": "UNKNOWN",
            "reasons": [result["error"]],
            "details": {}
        }
    
    return result

@app.get("/tokens/{address}/state")
async def get_token_state(address: str, rpc: str = "https://mainnet.base.org"):
    """Lightweight endpoint that returns raw on-chain state."""
    from .risk_scorer import get_b20_contract
    from web3 import Web3
    
    w3 = Web3(Web3.HTTPProvider(rpc))
    contract = get_b20_contract(w3, address)
    
    try:
        return {
            "paused": contract.functions.paused().call(),
            "supply_cap": contract.functions.supplyCap().call(),
            "total_supply": contract.functions.totalSupply().call(),
            "admin_has_role_zero": contract.functions.hasRole(
                "0x0000000000000000000000000000000000000000000000000000000000000000", 
                "0x0000000000000000000000000000000000000000"
            ).call(),
        }
    except Exception as e:
        return {"error": str(e)}

# TODO: Add endpoint for X sentiment once integrated
# TODO: Add WebSocket or polling endpoint for live new token alerts

# Gemini Agent Chat Endpoint
@app.post("/chat")
async def chat_with_agent(message: dict):
    """Chat with the B20 Pulse Gemini agent. Supports tool calling + streaming in full version."""
    try:
        from agent.gemini_agent import run_gemini_agent
        
        user_query = message.get("query", "")
        if not user_query:
            return {"error": "No query provided"}
        
        # For API, we run non-streaming and return full response
        # For true streaming, use StreamingResponse + SSE in production
        response = run_gemini_agent(user_query, stream=False)
        
        return {"response": response or "Sorry, I couldn't process that."}
    except Exception as e:
        return {"error": str(e)}
