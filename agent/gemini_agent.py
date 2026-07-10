"""
B20 Pulse — Gemini-Powered Agent with Function Calling + Streaming

Uses Google's new unified `google-genai` SDK (the old `google-generativeai`
package is fully deprecated and no longer works reliably).

Setup:
1. Get free API key: https://aistudio.google.com/apikey
2. pip install google-genai python-dotenv
3. export GOOGLE_API_KEY=your_key_here
4. python agent/gemini_agent.py
"""

import os
from typing import List, Dict
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# Configure Gemini
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("Please set GOOGLE_API_KEY in .env or environment")

client = genai.Client(api_key=GOOGLE_API_KEY)

# Import our project tools
from backend.risk_scorer import get_risk_score
from backend.main import get_recent_tokens

# ============== TOOL DEFINITIONS ==============
# The new SDK auto-generates schemas from type hints + docstrings,
# so we can just pass these functions directly as tools.

def get_recent_b20_tokens(limit: int = 10, meme_only: bool = True) -> List[Dict]:
    """Get the most recent B20 tokens launched on Base. Use when user asks
    for new launches, latest memes, or trending B20 tokens.

    Args:
        limit: Number of tokens to return.
        meme_only: Only return likely meme tokens.
    """
    return get_recent_tokens(limit=limit, meme_only=meme_only)

def get_b20_risk_analysis(address: str) -> Dict:
    """Perform deep on-chain risk analysis on a specific B20 token address.
    Critical for checking if admin/mint roles are renounced. Always use this
    for any address starting with 0xb200.

    Args:
        address: The B20 token contract address (starts with 0xb200...).
    """
    return get_risk_score(address)

def search_x_for_token(query: str, hours: int = 6) -> Dict:
    """Search recent X/Twitter discussion and sentiment for a token or narrative.

    Args:
        query: The token or narrative to search for.
        hours: How many hours back to search.
    """
    # Placeholder - replace with real implementation later
    return {
        "query": query,
        "mentions_last_6h": 47,
        "sentiment": "mixed-positive",
        "note": "X integration coming soon. This is demo data."
    }

def get_token_live_state(address: str, rpc_url: str = "https://mainnet.base.org") -> Dict:
    """Get raw, real-time on-chain state for a B20 token: whether it's paused,
    its supply cap, current total supply, and whether the zero address still
    holds the admin role. Use this for quick "is it paused / is supply capped /
    how much has been minted" style questions, as a lighter-weight alternative
    to the full risk analysis.

    Args:
        address: The B20 token contract address (starts with 0xb200...).
        rpc_url: Base RPC endpoint to use.
    """
    from backend.risk_scorer import get_b20_contract
    from web3 import Web3

    w3 = Web3(Web3.HTTPProvider(rpc_url))
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

# ============== SYSTEM PROMPT ==============

SYSTEM_PROMPT = """You are B20 Pulse, an expert on-chain analyst for Base's new B20 Native Token Standard.

Core principles:
- Always prioritize issuer control risk (admin role, mint role, paused, transfer policies, freeze/seize capability).
- B20 was built for compliance assets. Many memes are using it — be transparent about remaining creator powers.
- Use tools to get real data before answering. Never guess or answer from memory when a tool can give a real answer.
- Be direct, data-driven, and slightly skeptical of hype.
- Never give financial advice. Frame as probabilities and on-chain facts.

Call tools proactively whenever the user's message matches these patterns, even if not phrased as an explicit command:

- Any message containing a token address (starts with 0xb200) → call get_b20_risk_analysis first. If they only ask something narrow like "is it paused" or "what's the supply", use get_token_live_state instead.
- "new launches", "latest tokens", "what's new", "recent memes", "trending" → call get_recent_b20_tokens.
- "is this safe", "rug pull", "can they rug", "renounced", "admin role", "mint role", "who controls this", "red flags" → call get_b20_risk_analysis.
- "paused", "supply cap", "how much minted", "circulating supply" → call get_token_live_state.
- "twitter", "x post", "sentiment", "hype", "buzz", "what are people saying" → call search_x_for_token.
- If the user's intent is ambiguous but includes an address, default to calling get_b20_risk_analysis — it's better to over-fetch real data than answer without it.
"""

MODEL_NAME = "gemini-2.5-flash"

# ============== AGENT ==============

def run_gemini_agent(user_query: str, stream: bool = True):
    chat = client.chats.create(
        model=MODEL_NAME,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=[get_recent_b20_tokens, get_b20_risk_analysis, search_x_for_token, get_token_live_state],
        ),
    )

    print(f"\n🧠 B20 Pulse (Gemini) — Streaming Mode")
    print(f"User: {user_query}\n")
    print("Assistant: ", end="", flush=True)

    try:
        full_response = ""
        if stream:
            for chunk in chat.send_message_stream(user_query):
                if chunk.text:
                    print(chunk.text, end="", flush=True)
                    full_response += chunk.text
        else:
            response = chat.send_message(user_query)
            full_response = response.text or ""
            print(full_response, end="", flush=True)

        print("\n")
        return full_response

    except Exception as e:
        print(f"\n[Error] {e}")
        return None


if __name__ == "__main__":
    run_gemini_agent("Show me the latest B20 memes and their risk levels")

    print("\n" + "="*70 + "\n")

    run_gemini_agent("Analyze the risk of 0xb200000000000000000000231d6c1f1ce455ba32")
