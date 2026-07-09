# B20 Pulse — How to Run Everything (Updated July 9, 2026)

## 1. Python Scanner (Fastest to see real data)

```bash
cd scanner
python -m venv venv && source venv/bin/activate
pip install web3
python b20_scanner.py --rpc https://mainnet.base.org --last 5000
```

Output goes to `scanner/b20_output/`

## 2. FastAPI Backend + Risk Scorer

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install fastapi uvicorn web3 python-dotenv
uvicorn main:app --reload --port 8000
```

Then visit:
- http://localhost:8000/docs → Interactive Swagger UI
- http://localhost:8000/tokens/recent
- http://localhost:8000/tokens/0xb200.../risk

## 3. Simple Agent Demo

```bash
cd agent
pip install python-dotenv openai   # optional, for real LLM later
python simple_agent.py
```

It will demonstrate tool use with the risk scorer.

## 4. Mini App UI (Frontend)

```bash
cd mini-app
# If you haven't created it yet:
npm create minikit@latest .

# Then copy the components we generated into the project
npm run dev
```

Open http://localhost:3000 — you’ll see the clean table + floating AI chat.

## Full Local Stack (Recommended)

Terminal 1: Backend
```bash
cd backend && uvicorn main:app --reload
```

Terminal 2: Frontend (after setting up Mini App)
```bash
cd mini-app && npm run dev
```

Terminal 3 (optional): Live scanner in another window
```bash
cd scanner && python b20_scanner.py --live
```

## Next Improvements (Pick One)

- Connect the Mini App to the FastAPI backend (fetch live tokens + risk)
- Add real X search to the agent (using x_keyword_search or X API)
- Improve the risk scorer with more B20-specific policy checks
- Add WebSocket endpoint for real-time new token alerts
- Deploy backend to Railway / Fly.io and frontend to Vercel

Let me know which one you want to tackle next and I’ll generate the code.