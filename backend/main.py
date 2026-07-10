"""
B20 Pulse FastAPI Backend

Serves:
- Recent B20 tokens (from scanner or cache)
- Detailed on-chain risk analysis for any B20 token
- Simple health check
"""

import os
import json
import threading
import time
import traceback
from pathlib import Path
from datetime import datetime, timezone

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

# Import our modules
from .risk_scorer import get_risk_score, get_light_state

# Scanner output path
SCANNER_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "scanner" / "b20_output"
SCANNER_OUTPUT_PATH = SCANNER_OUTPUT_DIR / "b20_tokens.json"

app = FastAPI(
    title="B20 Pulse API",
    description="Backend for B20 token tracking, risk scoring, and AI agent tools on Base",
    version="0.1.0"
)

# CORS — configurable via env var
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
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
    """Map scanner's raw B20Token shape into TokenResponse shape."""
    return {
        "address": raw.get("token_address", ""),
        "name": raw.get("name", "Unknown"),
        "symbol": raw.get("symbol", "???"),
        "variant": raw.get("variant", "ASSET"),
        "age": _humanize_age(raw.get("timestamp", "")),
        "meme_score": raw.get("meme_score", 0),
        "risk_level": "UNKNOWN",
        "liquidity": None,
    }


def _run_background_scanner(
    rpc_url: str = "https://mainnet.base.org",
    catch_up_blocks: int = 5000,
    poll_interval: int = 15
):
    """
    Background thread: initial historical catch-up, then polls for new blocks.
    Safely handles errors and never crashes the thread.
    """
    try:
        # Lazy import to avoid startup dependency issues
        from scanner.b20_scanner import get_web3, scan_historical, save_output
        w3 = get_web3(rpc_url)
    except Exception as e:
        print(f"[scanner] Could not connect to RPC, background scanner disabled: {e}")
        return

    print(f"[scanner] Connected to Base (chainId: {w3.eth.chain_id}). Starting background scan.")

    all_tokens = []
    last_block = w3.eth.block_number

    # Initial catch-up with retry
    for attempt in range(3):
        try:
            current_block = w3.eth.block_number
            from_block = max(1, current_block - catch_up_blocks)
            all_tokens = scan_historical(w3, from_block, current_block)
            save_output(all_tokens, SCANNER_OUTPUT_DIR)
            print(f"[scanner] Initial catch-up found {len(all_tokens)} tokens.")
            last_block = current_block
            break
        except Exception as e:
            print(f"[scanner] Initial catch-up attempt {attempt + 1} failed: {e}")
            if attempt == 2:
                print("[scanner] Giving up on initial catch-up. Will try again in poll loop.")
            time.sleep(5)

    # Poll loop
    while True:
        try:
            current_block = w3.eth.block_number
            if current_block > last_block:
                # Prevent huge gap scans (e.g., after long downtime)
                scan_from = max(last_block + 1, current_block - 100)
                new_tokens = scan_historical(w3, scan_from, current_block)
                if new_tokens:
                    all_tokens = new_tokens + all_tokens
                    save_output(all_tokens, SCANNER_OUTPUT_DIR)
                    print(f"[scanner] Found {len(new_tokens)} new token(s) at block {current_block}.")
                last_block = current_block
        except Exception as e:
            print(f"[scanner] Error in poll loop: {e}")
            traceback.print_exc()
        time.sleep(poll_interval)


@app.on_event("startup")
def start_background_scanner():
    """Start the background scanner in a daemon thread."""
    thread = threading.Thread(
        target=_run_background_scanner,
        kwargs={
            "rpc_url": os.getenv("RPC_URL", "https://mainnet.base.org"),
            "catch_up_blocks": int(os.getenv("SCAN_CATCH_UP_BLOCKS", "5000")),
            "poll_interval": int(os.getenv("SCAN_POLL_INTERVAL", "15")),
        },
        daemon=True,
        name="B20Scanner"
    )
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


class ChatRequest(BaseModel):
    query: str


@app.get("/")
async def root():
    return {"message": "B20 Pulse API is live", "docs": "/docs"}


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "scanner_output_exists": SCANNER_OUTPUT_PATH.exists()
    }


@app.get("/tokens/recent", response_model=List[TokenResponse])
async def get_recent_tokens_route(
    limit: int = Query(20, ge=1, le=100),
    meme_only: bool = Query(False)
):
    """Get recent B20 tokens from scanner output."""
    return get_recent_tokens(limit=limit, meme_only=meme_only)


def get_recent_tokens(limit: int = 20, meme_only: bool = False):
    """
    Returns recent B20 tokens from scanner JSON output.
    Falls back to mock data if no scanner output exists yet.
    """
    if not SCANNER_OUTPUT_PATH.exists():
        # Fallback mock data
        mock = [
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
        ]
        return mock[:limit]

    try:
        with open(SCANNER_OUTPUT_PATH) as f:
            raw_tokens = json.load(f)
    except Exception as e:
        return [{"error": f"Failed to read scanner output: {e}"}]

    tokens = [_transform_scanner_token(t) for t in raw_tokens]

    if meme_only:
        tokens = [t for t in tokens if t.get("meme_score", 0) >= 30]

    return tokens[:limit]


def _lookup_creator_address(address: str) -> Optional[str]:
    """Look up a token's deployer from scanner output."""
    if not SCANNER_OUTPUT_PATH.exists():
        return None
    try:
        with open(SCANNER_OUTPUT_PATH) as f:
            raw_tokens = json.load(f)
    except Exception:
        return None
    
    target = address.lower()
    for t in raw_tokens:
        if t.get("token_address", "").lower() == target:
            return t.get("deployer")
    return None


def analyze_token_risk_sync(address: str, rpc_url: str = "https://mainnet.base.org") -> dict:
    """
    Run full on-chain risk analysis for a B20 token.
    Returns structured risk assessment or error dict.
    """
    # Validate address format
    if not address or len(address) != 42 or not address.lower().startswith("0xb200"):
        return {
            "error": f"Invalid B20 address: '{address}'. Must be 42 chars and start with 0xb200...",
            "address": address,
            "risk_score": 0,
            "risk_level": "INVALID",
            "reasons": ["Address format is invalid"],
            "details": {}
        }

    creator = _lookup_creator_address(address)
    
    try:
        result = get_risk_score(address, creator_address=creator, rpc_url=rpc_url)
        return result
    except Exception as e:
        return {
            "error": str(e),
            "address": address,
            "risk_score": 0,
            "risk_level": "ERROR",
            "reasons": [f"Analysis failed: {str(e)}"],
            "details": {"traceback": traceback.format_exc()}
        }


@app.get("/tokens/{address}/risk", response_model=RiskAnalysisResponse)
async def analyze_token_risk(
    address: str,
    rpc: str = Query("https://mainnet.base.org", description="Base RPC URL")
):
    """
    Run full on-chain risk analysis for a B20 token.
    """
    result = analyze_token_risk_sync(address, rpc_url=rpc)
    
    if "error" in result:
        # Return 200 with error details in body, or 400/500 depending on error type
        if result.get("risk_level") == "INVALID":
            raise HTTPException(status_code=400, detail=result)
        raise HTTPException(status_code=500, detail=result)
    
    return result


@app.get("/tokens/{address}/state")
async def get_token_state(address: str, rpc: str = "https://mainnet.base.org"):
    """
    Lightweight endpoint for raw on-chain state.
    """
    if not address or len(address) != 42 or not address.lower().startswith("0xb200"):
        raise HTTPException(status_code=400, detail="Invalid B20 address format")
    
    try:
        return get_light_state(address, rpc_url=rpc)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat")
async def chat_with_agent(request: ChatRequest):
    """
    Chat with the B20 Pulse Gemini agent.
    Non-streaming for API. For streaming, use SSE in production.
    """
    try:
        # Lazy import to avoid circular dependency
        from agent.gemini_agent import run_gemini_agent
        
        user_query = request.query.strip()
        if not user_query:
            raise HTTPException(status_code=400, detail="No query provided")
        
        response = run_gemini_agent(user_query, stream=False)
        
        if response is None:
            raise HTTPException(status_code=500, detail="Agent failed to generate response")
        
        return {"response": response, "success": True}
        
    except HTTPException:
        raise
    except Exception as e:
        traceback_str = traceback.format_exc()
        raise HTTPException(status_code=500, detail={
            "error": str(e),
            "traceback": traceback_str,
            "error_type": type(e).__name__
        })
