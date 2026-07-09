"""
B20 Pulse — Gemini-Powered Agent with Function Calling + Streaming

This is a production-ready agent example using Google's Gemini (free tier via Google AI Studio).

Features:
- Proper tool/function calling
- Streaming responses
- Uses the same tools as the rest of the project (risk scorer, recent tokens, etc.)
- Easy to swap to Grok / OpenAI later

Setup:
1. Get free API key: https://aistudio.google.com/app/apikey
2. pip install google-generativeai python-dotenv
3. export GOOGLE_API_KEY=your_key_here
4. python agent/gemini_agent.py

You can also integrate this into the Mini App chat.
"""

import os
import json
from typing import List, Dict, Any
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

# Configure Gemini
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("Please set GOOGLE_API_KEY in .env or environment")

genai.configure(api_key=GOOGLE_API_KEY)

# Import our project tools
from backend.risk_scorer import get_risk_score
from backend.main import get_recent_tokens

# ============== TOOL DEFINITIONS (Gemini format) ==============

def get_recent_b20_tokens(limit: int = 10, meme_only: bool = True) -> List[Dict]:
    """Get latest B20 tokens. Use this when user asks for new launches or memes."""
    return get_recent_tokens(limit=limit, meme_only=meme_only)

def get_b20_risk_analysis(address: str) -> Dict:
    """Run full on-chain risk analysis on a B20 token. Always use this for any address starting with 0xb200."""
    return get_risk_score(address)

def search_x_for_token(query: str, hours: int = 6) -> Dict:
    """Search recent discussion on X/Twitter about a token or narrative."""
    # Placeholder - replace with real implementation later
    return {
        "query": query,
        "mentions_last_6h": 47,
        "sentiment": "mixed-positive",
        "note": "X integration coming soon. This is demo data."
    }

# Map tool names to actual functions
AVAILABLE_TOOLS = {
    "get_recent_b20_tokens": get_recent_b20_tokens,
    "get_b20_risk_analysis": get_b20_risk_analysis,
    "search_x_for_token": search_x_for_token,
}

# Tool declarations for Gemini
TOOLS_DECLARATION = [
    {
        "name": "get_recent_b20_tokens",
        "description": "Get the most recent B20 tokens launched on Base. Use when user asks for new launches, latest memes, or trending B20 tokens.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Number of tokens to return"},
                "meme_only": {"type": "boolean", "description": "Only return likely meme tokens"}
            },
        },
    },
    {
        "name": "get_b20_risk_analysis",
        "description": "Perform deep on-chain risk analysis on a specific B20 token address. Critical for checking if admin/mint roles are renounced.",
        "parameters": {
            "type": "object",
            "properties": {
                "address": {"type": "string", "description": "The B20 token contract address (starts with 0xb200...)"}
            },
            "required": ["address"]
        },
    },
    {
        "name": "search_x_for_token",
        "description": "Search recent X/Twitter discussion and sentiment for a token or narrative.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "hours": {"type": "integer"}
            },
            "required": ["query"]
        },
    }
]

# ============== SYSTEM PROMPT ==============

SYSTEM_PROMPT = """You are B20 Pulse, an expert on-chain analyst for Base's new B20 Native Token Standard.

Core principles:
- Always prioritize issuer control risk (admin role, mint role, paused, transfer policies, freeze/seize capability).
- B20 was built for compliance assets. Many memes are using it — be transparent about remaining creator powers.
- Use tools to get real data before answering.
- Be direct, data-driven, and slightly skeptical of hype.
- Never give financial advice. Frame as probabilities and on-chain facts.

When user gives an address starting with 0xb200, always call get_b20_risk_analysis first.
"""

# ============== AGENT ==============

def run_gemini_agent(user_query: str, stream: bool = True):
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",  # Fast and free tier friendly
        tools=TOOLS_DECLARATION,
        system_instruction=SYSTEM_PROMPT
    )

    chat = model.start_chat(enable_automatic_function_calling=True)

    print(f"\n🧠 B20 Pulse (Gemini) — Streaming Mode")
    print(f"User: {user_query}\n")
    print("Assistant: ", end="", flush=True)

    try:
        response = chat.send_message(user_query, stream=stream)

        full_response = ""
        for chunk in response:
            if chunk.text:
                print(chunk.text, end="", flush=True)
                full_response += chunk.text

        print("\n")  # New line after streaming

        # Optional: Print tool calls made (for debugging)
        # You can inspect chat.history for function calls if needed

        return full_response

    except Exception as e:
        print(f"\n[Error] {e}")
        return None


if __name__ == "__main__":
    # Demo queries
    run_gemini_agent("Show me the latest B20 memes and their risk levels")
    
    print("\n" + "="*70 + "\n")
    
    run_gemini_agent("Analyze the risk of 0xb200000000000000000000231d6c1f1ce455ba32")
