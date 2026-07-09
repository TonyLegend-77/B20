# B20 Pulse — Interactive AI Agent for B20 Memecoins on Base

**Live B20 token tracker + conversational AI analyst**, built as a **Base Mini App** for seamless access inside the Base App.

**Status**: Starter files generated — ready for you to run locally and iterate in Cursor / VS Code.

## Why This Matters Right Now (July 9, 2026)
- B20 Native Token Standard went live on Base mainnet **July 8, 2026**.
- New B20 tokens are launching rapidly (many memes).
- Built-in compliance features + fair-launch launchpads (Berylpad, b20.mom, etc.) = new meta.
- Perfect timing for an on-chain + social intelligence agent.

## Project Goals
- Real-time detection of new B20 tokens (especially memes).
- AI-powered analysis & natural language chat.
- Risk scoring (issuer controls, liquidity, hype).
- Accessible **inside Base App** as a Mini App (social discovery + instant wallet).
- Extensible to alerts, sniping signals, portfolio tracking.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     B20 Pulse (Mini App)                     │
│  (Next.js + MiniKit + OnchainKit — runs inside Base App)    │
├─────────────────────────────────────────────────────────────┤
│  Frontend: Live table + AI Chat sidebar + Alerts            │
│  - React + Tailwind + shadcn/ui                             │
│  - Base Account (smart wallet) auto-connected               │
│  - Share to Base feed / Farcaster                           │
├─────────────────────────────────────────────────────────────┤
│  Backend / Agent Layer (FastAPI or serverless)              │
│  - B20 Scanner (web3.py or ethers)                          │
│  - Risk Scorer (on-chain state + heuristics)                │
│  - LLM Tool-calling Agent (Grok API / OpenAI)               │
│  - X Sentiment tool                                         │
│  - Price / Liquidity (Uniswap/Aerodrome)                    │
├─────────────────────────────────────────────────────────────┤
│  Data Sources                                               │
│  - Base RPC (mainnet.base.org)                              │
│  - B20Factory B20Created events                             │
│  - Coinbase CDP SQL (optional, more reliable)               │
│  - DEX subgraphs / APIs                                     │
│  - X (Twitter) API or free search                           │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start (Local Development)

### 1. B20 Scanner (Python) — Most Important First Piece
```bash
cd scanner
python -m venv venv
source venv/bin/activate
pip install web3 python-dotenv
python b20_scanner.py --rpc https://mainnet.base.org --last 5000
```

This will output recent B20 tokens + basic meme classification.

### 2. Mini App (Next.js + Base MiniKit)
Follow the scaffold in `/mini-app/`

### 3. Run the AI Agent
Use the prompts in `/prompts/` + tools in `/agent/`

## Detailed UI Flows (Designed for Base App)

### Screen 1: Home / Live Feed (Default on open)
- Top bar: "B20 Pulse • Live on Base" + connected wallet (Base Account)
- Tabs: **All B20** | **Memes Only** | **Trending** | **New (last 1h)**
- Table columns:
  - Token (name + symbol + 0xB200... address — clickable to analyzer)
  - Age (time since creation)
  - MC / Liquidity (if pool exists)
  - Risk Score (0-100 with color: Green/Yellow/Red)
  - Hype (X mentions + volume)
  - Quick Actions: Import | Trade | Analyze with AI | Share

**Interaction**:
- Click row → Opens **Token Detail Drawer**
- Floating AI Chat button (bottom right) always available

### Screen 2: Token Detail + AI Analysis
- Header: Token name/symbol + copy address + "Open in Basescan / Uniswap"
- On-chain Snapshot (fetched live):
  - Variant (ASSET / STABLECOIN)
  - Decimals
  - Total Supply + Cap (if set)
  - Admin / Mint / Burn roles status (renounced? still held by creator?)
  - Transfer policies active?
  - Paused?
  - Freeze/Seize capability remaining?
- Liquidity & Price section (DEX data)
- AI Summary Card (auto-generated or on-demand):
  > "This looks like a classic early meme launch. Creator still holds mint role (high risk). No liquidity yet. Low X volume so far. Fair launch template used on Berylpad."

- Chat input: "Is the mint role renounced?" / "Compare to $BPEPE" / "What's the narrative?"

### Screen 3: AI Chat (Conversational Mode)
Global chat that remembers context:
- "Show me the 5 newest B20 memes with renounced admin"
- "Alert me when a new B20 with >$50k liquidity and renounced roles launches"
- "What’s pumping in B20 right now?"

The agent uses tools to answer accurately.

### Screen 4: Alerts & Watchlist
- Create alerts: "New B20 meme + renounced roles + liquidity added"
- In-app notifications (or push via Base.dev)
- Watchlist tokens with live updates

## Risk Scoring Logic (Core Intelligence)

**Score = 100 (Safest) down to 0 (High Risk)**

**Positive signals (+)**:
- Admin role renounced or burned
- Mint role renounced
- Supply cap set and reasonable
- No active transfer policies / allowlists (or community-gated fairly)
- Liquidity added quickly after creation (fair launch signal)
- Launched via reputable B20 launchpad (Berylpad template with renounces)
- Some organic X volume within first hours

**Negative signals (−)**:
- Creator still holds DEFAULT_ADMIN_ROLE or MINT_ROLE (can mint more or seize)
- Transfer policies active (can block sellers)
- Paused state
- No liquidity after reasonable time
- Extremely low decimals or weird supply (manipulation risk)
- Creator wallet has history of many quick rug-like launches (future enhancement)

**Implementation**:
- Query token contract directly using IB20 interface (roles, paused, policies, supplyCap).
- Check recent transactions for renounce calls.
- Cross with DEX pool age.
- Simple heuristic in scanner first, then LLM refines the narrative.

Full logic documented in `docs/risk-scoring.md` (to be expanded).

## X Sentiment Integration
- Tool: `search_x_for_token(symbol_or_name)` using advanced X search.
- Metrics: Recent mentions count, sentiment keywords (ape, moon, rug, based, etc.), top posts.
- In starter: Mock data or manual trigger. Production: Use X API bearer or Grok's X tools.

## Price & Liquidity Feeds
- Primary: Uniswap V3/V4 + Aerodrome on Base (via subgraph or direct RPC + quoter).
- Fallback: Public DEX aggregators or CoinGecko (if listed).
- For new tokens without pool yet: Show "No liquidity yet" + bonding curve progress if from launchpad.

## Agent System Prompt (Core Personality)
See `prompts/b20_analyst_prompt.md`

Key traits:
- Sharp on-chain analyst first, meme degen second.
- Always checks renounced roles + issuer control risk.
- Transparent about B20 being a compliance standard that memes are riding.
- Never gives financial advice — frames as data + probabilities.
- Uses tools rigorously before answering.

## Next Steps & Roadmap (What We Build Next)

**Immediate (You can do today)**:
1. Run the Python scanner and see live B20 tokens.
2. Scaffold the Next.js Mini App.
3. Test the agent prompt in Cursor with Grok or Claude.

**Week 1**:
- Full Mini App with live table + basic chat.
- On-chain risk scorer (query roles/paused).
- Deploy as Mini App to Base.dev.

**Week 2+**:
- Real X sentiment tool.
- Price/liquidity integration.
- Alert system + notifications.
- Advanced agent (multi-step reasoning, portfolio mode).
- Optional: On-chain agent components (verifiable via BOT Chain or similar if you pursue hackathons).

## Files Included in This Starter

- `scanner/b20_scanner.py` — Production-ready B20Created event scanner
- `prompts/b20_analyst_prompt.md` — Full system prompt + few-shot examples
- `agent/` — Tool definitions and simple agent runner example
- `mini-app/` — MiniKit scaffold + key React components
- `docs/` — Additional guides (risk logic, deployment)

---

**Let's ship this.**

Run the scanner first to see real data, then tell me:
- "Build the Mini App frontend next"
- "Improve the risk scorer"
- "Add X search tool"
- Or any specific part you want to tackle.

I'm ready to generate more code, refine prompts, or debug as we go. 

**Tony — this has strong potential.** B20 is brand new and the timing for a dedicated intelligence layer is perfect. Let's make B20 Pulse the go-to agent for the new meta.