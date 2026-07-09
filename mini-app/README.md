# B20 Pulse Mini App — Base App Scaffold

This is the **Mini App** version of B20 Pulse that will run **inside the Base App**.

Built with **MiniKit** (official Base tooling) + OnchainKit for seamless Base Account integration.

## Quick Start (Local)

```bash
# 1. Create new Mini App
npm create minikit@latest b20-pulse-mini
cd b20-pulse-mini

# 2. Install dependencies
npm install @coinbase/onchainkit wagmi viem @tanstack/react-query

# 3. Replace key files with the ones in this folder (or copy logic)

# 4. Run dev server
npm run dev
```

Then open in browser and test. Later deploy to Vercel and register on Base.dev for discovery inside Base App.

## Key Files in This Scaffold

- `app/page.tsx` — Main UI with live table + AI chat
- `components/TokenTable.tsx` — Reusable table component
- `components/AIChat.tsx` — Chat interface with tool calling
- `lib/b20.ts` — On-chain helpers (get recent tokens, token state)
- `app/manifest.json` or metadata for Mini App discovery

## Important Mini App Concepts

- Uses **Base Account** (smart wallet) — users are automatically connected when they open your Mini App inside Base App.
- Social-native: Easy sharing to feed, notifications, etc.
- Gas sponsorship possible via paymaster.
- Works in Base App + Farcaster clients.

## UI Flow Implemented in Starter

1. **Home Screen**
   - Header with "B20 Pulse" + wallet status
   - Tabs: New | Memes | Trending
   - Live updating table (mock data for now → connect to your Python scanner or a backend API)

2. **Token Row Click**
   - Opens side drawer or modal with:
     - On-chain snapshot
     - Risk score + explanation
     - "Ask AI about this token" button (opens chat pre-filled)

3. **Global AI Chat**
   - Bottom-right floating button
   - Full-screen or drawer chat
   - Uses the `b20_analyst_prompt.md` system prompt + tools

## Connecting Real Data

**Option A (Fastest for MVP)**: Call your Python scanner via a simple FastAPI backend you deploy (Railway / Fly.io / Vercel Functions).

**Option B**: Use direct RPC calls from the frontend (wagmi + viem) to read B20Factory events and token state. Good for read-only.

**Option C (Best long-term)**: Index B20 events into a database (Supabase + webhook or CDP SQL) and expose clean API endpoints.

## Next Code to Generate

Tell me which file you want expanded first:
- Full `page.tsx` with nice Tailwind + shadcn style
- Token detail drawer component
- Real tool-calling chat implementation (using Vercel AI SDK + Grok)
- Backend API route examples

We can make this look and feel native to Base App very quickly.