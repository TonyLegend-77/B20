"""
B20 Pulse — Simple Tool-Calling Agent Example

This is a minimal runnable example of the AI agent using the system prompt
and the tools we defined.

It uses a simple loop (no LangGraph yet) so you can run it immediately.

Requirements:
    pip install openai python-dotenv   # or use Grok API / Anthropic

Usage:
    export OPENAI_API_KEY=sk-...
    python agent/simple_agent.py

You can swap the LLM client for Grok, Claude, or local models.
"""

import os
import json
from typing import List, Dict, Any
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Import our tools
from backend.risk_scorer import get_risk_score
from backend.main import get_recent_tokens   # reuse FastAPI logic or import directly

# System prompt (loaded from file in real version)
SYSTEM_PROMPT = """
You are B20 Pulse, a sharp on-chain analyst for Base's B20 token standard.
Always check issuer control risk first (admin/mint roles, paused, policies).
Be direct and data-driven. Never give financial advice.
Use tools when needed. Format final answers clearly.
"""

# Tool definitions (OpenAI / Grok compatible format)
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_recent_b20_tokens",
            "description": "Get the most recent B20 tokens launched on Base",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 10},
                    "meme_only": {"type": "boolean", "default": True}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_b20_risk_analysis",
            "description": "Run full on-chain risk analysis on a specific B20 token address",
            "parameters": {
                "type": "object",
                "properties": {
                    "address": {"type": "string", "description": "B20 token contract address starting with 0xb200..."}
                },
                "required": ["address"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_x_for_token",
            "description": "Search recent X (Twitter) posts about a token or narrative",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "hours": {"type": "integer", "default": 6}
                }
            }
        }
    }
]

def call_tool(tool_name: str, arguments: Dict[str, Any]) -> Any:
    """Execute a tool by name."""
    if tool_name == "get_recent_b20_tokens":
        return get_recent_tokens(limit=arguments.get("limit", 10), meme_only=arguments.get("meme_only", True))
    
    elif tool_name == "get_b20_risk_analysis":
        return get_risk_score(arguments["address"])
    
    elif tool_name == "search_x_for_token":
        # Placeholder — replace with real X search later
        return {
            "query": arguments.get("query"),
            "mentions_6h": 42,
            "sentiment": "mixed",
            "note": "X integration coming soon. This is mock data."
        }
    
    return {"error": f"Unknown tool: {tool_name}"}

def run_agent(user_query: str, max_steps: int = 5):
    """
    Very simple ReAct-style loop.
    In production use LangGraph, CrewAI, or Vercel AI SDK for better control.
    """
    print(f"\n🧠 B20 Pulse Agent")
    print(f"User: {user_query}\n")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_query}
    ]

    for step in range(max_steps):
        # In real implementation: call LLM with tools
        # Here we simulate smart behavior for demo purposes
        print(f"[Step {step+1}] Thinking...")

        # Demo logic (replace with real LLM tool calling)
        if "latest" in user_query.lower() or "new" in user_query.lower():
            result = call_tool("get_recent_b20_tokens", {"limit": 5, "meme_only": True})
            print("→ Using tool: get_recent_b20_tokens")
            print(json.dumps(result, indent=2))
            break

        elif "0xb200" in user_query:
            # Extract address (very naive)
            import re
            match = re.search(r"0xb200[0-9a-fA-F]+", user_query)
            if match:
                addr = match.group(0)
                result = call_tool("get_b20_risk_analysis", {"address": addr})
                print(f"→ Using tool: get_b20_risk_analysis on {addr}")
                print(json.dumps(result, indent=2))
                break

        else:
            print("→ No tool needed or query not specific enough. Answering directly.")
            print("B20 Pulse: I can check recent launches or analyze any 0xb200... address. Try one of those!")
            break

    print("\n[Agent finished]")

if __name__ == "__main__":
    # Demo queries
    run_agent("Show me the latest B20 memes")
    print("\n" + "="*60 + "\n")
    run_agent("Analyze 0xb200000000000000000000231d6c1f1ce455ba32")