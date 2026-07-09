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
from pathlib import Path
from datetime import datetime

# Import our modules
from .risk_scorer import get_risk_score
# from scanner.b20_scanner import scan_historical   # optional: import live scanner

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
async def get_recent_tokens(
    limit: int = Query(20, ge=1, le=100),
    meme_only: bool = Query(False)
):
    """
    Returns recent B20 tokens.
    For MVP we read from a JSON file produced by the scanner.
    In production: connect to live scanner or database.
    """
    output_path = Path("../scanner/b20_output/b20_tokens.json")
    
    if not output_path.exists():
        # Fallback mock data
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
        tokens = json.load(f)

    if meme_only:
        tokens = [t for t in tokens if t.get("is_likely_meme")]

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