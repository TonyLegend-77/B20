"""
B20 Pulse — Gemini-Powered Agent with Function Calling + Streaming

Uses Google's unified `google-genai` SDK.
"""

import os
import json
import traceback
from typing import List, Dict, Any
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("Please set GOOGLE_API_KEY in .env or environment")

client = genai.Client(api_key=GOOGLE_API_KEY)

# Import tools safely — avoid circular imports by importing at function level
def _import_backend():
    """Lazy import to avoid circular dependency issues."""
    from backend.risk_scorer import get_light_state, get_risk_score
    from backend.main import get_recent_tokens, analyze_token_risk_sync
    return get_light_state, get_risk_score, get_recent_tokens, analyze_token_risk_sync

# ============== TOOL DEFINITIONS (Explicit JSON Schema for Gemini) ==============

TOOL_GET_RECENT_TOKENS = types.FunctionDeclaration(
    name="get_recent_b20_tokens",
    description="Get the most recent B20 tokens launched on Base. Use when user asks for new launches, latest memes, or trending B20 tokens.",
    parameters=types.Schema(
        type="object",
        properties={
            "limit": types.Schema(type="integer", description="Number of tokens to return (1-100)"),
            "meme_only": types.Schema(type="boolean", description="Only return likely meme tokens")
        }
    )
)

TOOL_GET_RISK_ANALYSIS = types.FunctionDeclaration(
    name="get_b20_risk_analysis",
    description="Perform deep on-chain risk analysis on a specific B20 token address. Critical for checking if admin/mint roles are renounced. Always use this for any address starting with 0xb200.",
    parameters=types.Schema(
        type="object",
        properties={
            "address": types.Schema(type="string", description="The B20 token contract address (starts with 0xb200...)"),
            "rpc_url": types.Schema(type="string", description="Base RPC endpoint. Default: https://mainnet.base.org")
        },
        required=["address"]
    )
)

TOOL_GET_LIVE_STATE = types.FunctionDeclaration(
    name="get_token_live_state",
    description="Get raw, real-time on-chain state for a B20 token: which features are currently paused, its supply cap, and current total supply. Use this for quick 'is it paused / is supply capped / how much has been minted' questions.",
    parameters=types.Schema(
        type="object",
        properties={
            "address": types.Schema(type="string", description="The B20 token contract address (starts with 0xb200...)"),
            "rpc_url": types.Schema(type="string", description="Base RPC endpoint. Default: https://mainnet.base.org")
        },
        required=["address"]
    )
)

TOOL_SEARCH_X = types.FunctionDeclaration(
    name="search_x_for_token",
    description="Search recent X/Twitter discussion and sentiment for a token or narrative.",
    parameters=types.Schema(
        type="object",
        properties={
            "query": types.Schema(type="string", description="The token or narrative to search for"),
            "hours": types.Schema(type="integer", description="How many hours back to search. Default: 6")
        },
        required=["query"]
    )
)

ALL_TOOLS = [
    types.Tool(function_declarations=[
        TOOL_GET_RECENT_TOKENS,
        TOOL_GET_RISK_ANALYSIS,
        TOOL_GET_LIVE_STATE,
        TOOL_SEARCH_X,
    ])
]

# ============== SYSTEM PROMPT ==============

SYSTEM_PROMPT = """You are B20 Pulse, an expert on-chain analyst for Base's new B20 Native Token Standard.

Core principles:
- Always prioritize issuer control risk (admin role, mint role, paused, transfer policies, freeze/seize capability).
- B20 was built for compliance assets. Many memes are using it — be transparent about remaining creator powers.
- Use tools to get real data before answering. Never guess or answer from memory when a tool can give a real answer.
- Be direct, data-driven, and slightly skeptical of hype.
- Never give financial advice. Frame as probabilities and on-chain facts.

ADDRESS VALIDATION:
- B20 addresses MUST start with '0xb200' (case-insensitive check: 0xb200...).
- If a user provides an address that does not start with '0xb200', tell them it's not a valid B20 address and ask them to double-check.
- Do NOT call tools with invalid addresses.

Call tools proactively whenever the user's message matches these patterns:
- Any message containing a token address (starts with 0xb200) → call get_b20_risk_analysis first. If they only ask something narrow like "is it paused" or "what's the supply", use get_token_live_state instead.
- "new launches", "latest tokens", "what's new", "recent memes", "trending" → call get_recent_b20_tokens.
- "is this safe", "rug pull", "can they rug", "renounced", "admin role", "mint role" → call get_b20_risk_analysis.
- "paused", "supply cap", "how much minted", "circulating supply" → call get_token_live_state.
- "twitter", "x post", "sentiment", "hype", "buzz" → call search_x_for_token.
"""

MODEL_NAME = "gemini-2.5-flash"

# ============== TOOL EXECUTION ==============

def _is_valid_b20_address(address: str) -> bool:
    """Validate B20 address format."""
    if not address or not isinstance(address, str):
        return False
    return len(address) == 42 and address.lower().startswith("0xb200")

def _execute_tool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a tool by name with given arguments. Returns structured result or error."""
    get_light_state, get_risk_score, get_recent_tokens, analyze_token_risk_sync = _import_backend()
    
    try:
        if name == "get_recent_b20_tokens":
            limit = min(max(args.get("limit", 10), 1), 100)
            meme_only = args.get("meme_only", True)
            tokens = get_recent_tokens(limit=limit, meme_only=meme_only)
            return {"success": True, "data": tokens}
        
        elif name == "get_b20_risk_analysis":
            address = args.get("address", "")
            if not _is_valid_b20_address(address):
                return {
                    "success": False,
                    "error": f"Invalid B20 address: '{address}'. B20 addresses must start with '0xb200...' and be 42 characters long.",
                    "is_invalid_address": True
                }
            rpc_url = args.get("rpc_url", "https://mainnet.base.org")
            result = analyze_token_risk_sync(address, rpc_url=rpc_url)
            return {"success": True, "data": result}
        
        elif name == "get_token_live_state":
            address = args.get("address", "")
            if not _is_valid_b20_address(address):
                return {
                    "success": False,
                    "error": f"Invalid B20 address: '{address}'. B20 addresses must start with '0xb200...' and be 42 characters long.",
                    "is_invalid_address": True
                }
            rpc_url = args.get("rpc_url", "https://mainnet.base.org")
            result = get_light_state(address, rpc_url=rpc_url)
            return {"success": True, "data": result}
        
        elif name == "search_x_for_token":
            query = args.get("query", "")
            hours = args.get("hours", 6)
            # Placeholder — replace with real implementation
            return {
                "success": True,
                "data": {
                    "query": query,
                    "mentions_last_6h": 47,
                    "sentiment": "mixed-positive",
                    "note": "X integration coming soon. This is demo data."
                }
            }
        
        else:
            return {"success": False, "error": f"Unknown tool: {name}"}
            
    except Exception as e:
        traceback_str = traceback.format_exc()
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback_str,
            "error_type": type(e).__name__
        }

# ============== AGENT ==============

def _format_tool_result(tool_name: str, result: Dict[str, Any]) -> str:
    """Format tool result for the LLM context."""
    if result.get("success"):
        return json.dumps(result.get("data"), indent=2)
    else:
        error_msg = result.get("error", "Unknown error")
        if result.get("is_invalid_address"):
            return f"ERROR: {error_msg}\nDo not attempt to call other tools with this address. Inform the user clearly."
        return f"ERROR executing {tool_name}: {error_msg}"

def run_gemini_agent(user_query: str, stream: bool = True):
    """
    Run the Gemini agent with tool calling.
    Returns the full response string, or None on fatal error.
    """
    chat = client.chats.create(
        model=MODEL_NAME,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=ALL_TOOLS,
            temperature=0.2,
        ),
    )

    if stream:
        print(f"\n🧠 B20 Pulse (Gemini) — Streaming Mode")
    print(f"User: {user_query}\n")
    print("Assistant: ", end="", flush=True)

    try:
        # First message from user
        response = chat.send_message(user_query)
        
        # Handle tool calls
        max_tool_rounds = 5
        for round_num in range(max_tool_rounds):
            # Check if the model wants to call tools
            if not response.candidates or not response.candidates[0].content or not response.candidates[0].content.parts:
                break
                
            parts = response.candidates[0].content.parts
            tool_calls = [p for p in parts if p.function_call]
            
            if not tool_calls:
                # No more tool calls, we have the final answer
                break
            
            # Execute all tool calls
            tool_results = []
            for part in tool_calls:
                fc = part.function_call
                tool_name = fc.name
                tool_args = dict(fc.args) if fc.args else {}
                
                print(f"\n[Tool Call] {tool_name}({json.dumps(tool_args)})")
                
                result = _execute_tool(tool_name, tool_args)
                formatted_result = _format_tool_result(tool_name, result)
                
                tool_results.append(
                    types.Part.from_function_response(
                        name=tool_name,
                        response={"result": formatted_result}
                    )
                )
            
            # Send tool results back to model
            response = chat.send_message(tool_results)
        
        # Extract final text
        final_text = ""
        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.text:
                    final_text += part.text
        
        print(final_text)
        print("\n")
        return final_text

    except Exception as e:
        error_msg = f"\n[Fatal Error] {type(e).__name__}: {e}\n{traceback.format_exc()}"
        print(error_msg)
        return None


if __name__ == "__main__":
    # Test cases
    print("=" * 70)
    print("TEST 1: Recent tokens")
    run_gemini_agent("Show me the latest B20 memes and their risk levels", stream=False)
    
    print("\n" + "=" * 70 + "\n")
    print("TEST 2: Valid B20 address")
    run_gemini_agent("Analyze the risk of 0xb200000000000000000000231d6c1f1ce455ba32", stream=False)
    
    print("\n" + "=" * 70 + "\n")
    print("TEST 3: Invalid address (should fail gracefully)")
    run_gemini_agent("analyze this 0xeD664536023d8E4b1640C394777D34aBAFF1dF8F", stream=False)
