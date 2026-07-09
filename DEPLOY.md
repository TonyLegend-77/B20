# B20 Pulse — Deployment Guide (July 2026)

This guide covers deploying:
- **Backend (FastAPI + Risk Scorer)** → Railway (recommended) or Fly.io
- **Mini App (Next.js + MiniKit)** → Vercel

## 1. Backend Deployment (Railway — Easiest)

### Step-by-step

1. **Prepare your code**
   - Make sure `backend/` folder has:
     - `main.py`
     - `risk_scorer.py`
     - `requirements.txt` (create it)

2. **Create `backend/requirements.txt`**
```txt
fastapi
uvicorn[standard]
web3
python-dotenv
pydantic
```

3. **Push to GitHub** (recommended)
   - Create a repo (e.g. `b20-pulse`)
   - Push the whole `b20-pulse` folder (or at least the `backend` folder)

4. **Deploy on Railway**
   - Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
   - Select your repo
   - Railway will auto-detect Python + FastAPI
   - Set **Root Directory** to `backend` (important)
   - Add environment variable:
     - `PYTHONPATH` = `.` (sometimes needed)

5. **After deployment**
   - Railway gives you a public URL like: `https://b20-pulse-backend-production.up.railway.app`
   - Test it: `https://your-url.up.railway.app/docs`

6. **(Optional) Add custom domain** later in Railway settings.

---

## 2. Mini App Deployment (Vercel)

### Step-by-step

1. **Prepare the Mini App**
   - Make sure you have a working Next.js + MiniKit project in `mini-app/`
   - Create `mini-app/.env.local` (or use Vercel env vars):
     ```env
     NEXT_PUBLIC_API_URL=https://your-railway-backend-url.up.railway.app
     ```

2. **Push to GitHub** (same repo or separate)

3. **Deploy on Vercel**
   - Go to [vercel.com](https://vercel.com) → New Project
   - Import your GitHub repo
   - Set **Root Directory** to `mini-app`
   - Add Environment Variable:
     - `NEXT_PUBLIC_API_URL` = `https://your-railway-backend.up.railway.app`
   - Deploy

4. **After deployment**
   - Vercel gives you a URL like `https://b20-pulse-mini.vercel.app`
   - Update your Railway backend CORS if needed (allow the Vercel domain)

---

## 3. Environment Variables Summary

| Service     | Variable                    | Example Value                              | Where to set     |
|-------------|-----------------------------|--------------------------------------------|------------------|
| Backend     | (none critical)             | -                                          | Railway          |
| Mini App    | `NEXT_PUBLIC_API_URL`       | `https://b20-pulse-backend.up.railway.app` | Vercel           |
| Agent (local)| `GOOGLE_API_KEY`           | Your Gemini key                            | `.env` file      |

---

## 4. Alternative: Fly.io (Backend)

If you prefer Fly.io:

```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

cd backend
fly launch
fly deploy
```

Fly.io is great if you want more control or lower cost at scale.

---

## 5. Production Recommendations

- **CORS**: In production, restrict `allow_origins` in `backend/main.py` to only your Vercel domain.
- **Rate limiting**: Add slowapi or similar on public endpoints.
- **Monitoring**: Railway and Vercel have good built-in logs + metrics.
- **Custom domain**: Point a subdomain (e.g. `pulse.yourdomain.com`) to Vercel.
- **API Key protection**: If you add paid APIs later (X, etc.), store keys only on backend.

---

## 6. Quick Verification Checklist

After deployment:
- [ ] Backend `/docs` loads
- [ ] `/tokens/recent` returns data
- [ ] `/tokens/0xb200.../risk` returns real risk analysis
- [ ] Mini App loads and shows real tokens from your backend
- [ ] Clicking a token shows live risk data from backend
- [ ] AI Chat works (if connected to agent)

---

You now have a full production-ready stack.

Would you like me to also generate:
- A `railway.json` or `fly.toml` config?
- Updated CORS settings for production?
- A one-click deploy button template?

Just say the word.