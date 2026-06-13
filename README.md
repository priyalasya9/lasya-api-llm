# AI Chat Application

A production-quality mini AI chat app built with **Streamlit + FastAPI + SQLite + OpenAI**.

| Layer | Technology |
|---|---|
| Frontend | Streamlit |
| Backend | FastAPI |
| Database | SQLite (SQLAlchemy ORM) |
| AI | OpenAI `gpt-4o-mini` |

---

## Features

- **Multi-thread chat** — create, rename, and switch between independent conversations
- **Full message history** — every message persisted to SQLite and restored on revisit
- **Universal memory** — facts shared in any thread are remembered across all future threads
- **Production-ready** — environment-based config, startup validation, CORS controls, no hardcoded secrets

---

## Project Structure

```
lasya-api-llm/
├── app.py           # FastAPI backend — routes, LLM calls, memory logic
├── database.py      # SQLAlchemy models and session factory
├── main.py          # Streamlit frontend
├── render.yaml      # Render Blueprint — deploys both services automatically
├── runtime.txt      # Pins Python 3.11 for all platforms
├── requirements.txt # Pinned Python dependencies
├── .env.example     # Environment variable template (copy → .env for local dev)
├── .gitignore       # Excludes .env, *.db, venv, __pycache__, etc.
└── README.md
```

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | **Yes** | — | OpenAI secret key (`sk-proj-...`) |
| `LLM_MODEL` | No | `gpt-4o-mini` | Any OpenAI chat model |
| `DATABASE_URL` | No | `sqlite:///./chats.db` | SQLAlchemy connection string |
| `ALLOWED_ORIGINS` | No | `http://localhost:8501,...` | Comma-separated CORS origins for the backend |
| `API_BASE` | No | `http://localhost:8000` | Backend URL used by the Streamlit frontend |

---

## Deployment — Render (Recommended)

Render deploys both services (backend + frontend) automatically from `render.yaml`.  
No CLI required — everything is done through the Render dashboard.

### Step 1 — Create a Render account

Go to **https://render.com** → sign up (free tier is sufficient).

### Step 2 — Connect your GitHub repository

1. In the Render dashboard, click **"New"** → **"Blueprint"**
2. Click **"Connect a repository"**
3. Authorise Render to access your GitHub account
4. Select **`priyalasya9/lasya-api-llm`**
5. Select the branch **`claude/nifty-davinci-981uo7`**
6. Render detects `render.yaml` and shows two services:
   - `lasya-chat-backend` (FastAPI)
   - `lasya-chat-frontend` (Streamlit)
7. Click **"Apply"** — Render begins building both services

### Step 3 — Set the secret environment variables

Render will not deploy the backend until `OPENAI_API_KEY` is set.

**For `lasya-chat-backend`:**

1. Go to Dashboard → `lasya-chat-backend` → **Environment**
2. Add:

| Key | Value |
|---|---|
| `OPENAI_API_KEY` | `sk-proj-your-real-key-here` |
| `ALLOWED_ORIGINS` | `https://lasya-chat-frontend.onrender.com` |

**For `lasya-chat-frontend`:**

1. Go to Dashboard → `lasya-chat-frontend` → **Environment**
2. Add:

| Key | Value |
|---|---|
| `API_BASE` | `https://lasya-chat-backend.onrender.com` |

> **Note:** The exact URLs follow the pattern `https://<service-name>.onrender.com`.  
> You can see the assigned URL on each service's dashboard page.

### Step 4 — Trigger a redeploy

After setting environment variables:

1. Go to each service → click **"Manual Deploy"** → **"Deploy latest commit"**
2. Wait for both builds to show **"Live"** (≈ 2–4 minutes each)

### Step 5 — Access the live application

| Service | URL |
|---|---|
| **Frontend (Streamlit)** | `https://lasya-chat-frontend.onrender.com` |
| **Backend (FastAPI)** | `https://lasya-chat-backend.onrender.com` |
| **API Docs (Swagger)** | `https://lasya-chat-backend.onrender.com/docs` |
| **Health check** | `https://lasya-chat-backend.onrender.com/health` |

> **Free tier note:** Render's free services spin down after 15 minutes of inactivity.  
> The first request after a sleep takes ~30 seconds to wake up. This is normal.

---

## Important: SQLite on Render

Render's free tier uses an **ephemeral filesystem** — the `chats.db` file is wiped on every deploy.  
Chat history and memory are lost after each deployment.

**This is acceptable for demos and interviews.**

For persistent data, upgrade to a Render Postgres database and set:
```
DATABASE_URL=postgresql://user:password@host/dbname
```

---

## Local Development

### 1 · Clone the repository

```bash
git clone https://github.com/priyalasya9/lasya-api-llm.git
cd lasya-api-llm
git checkout claude/nifty-davinci-981uo7
```

### 2 · Create virtual environment

```bash
# Linux / macOS
python3 -m venv venv && source venv/bin/activate

# Windows PowerShell
python -m venv venv
venv\Scripts\Activate.ps1
```

> Windows tip — if blocked by execution policy, run once:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

### 3 · Install dependencies

```bash
pip install -r requirements.txt
```

### 4 · Configure environment

```bash
# Linux / macOS
cp .env.example .env

# Windows
copy .env.example .env
```

Edit `.env`:
```dotenv
OPENAI_API_KEY=sk-proj-your-real-key-here
```

### 5 · Run backend (Terminal 1)

```bash
uvicorn app:app --reload
# → http://127.0.0.1:8000
```

### 6 · Run frontend (Terminal 2)

```bash
streamlit run main.py
# → http://localhost:8501
```

---

## API Reference

Interactive docs at `http://localhost:8000/docs` (local) or `https://lasya-chat-backend.onrender.com/docs` (production).

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness probe |
| `POST` | `/threads` | Create a chat thread |
| `GET` | `/threads` | List all threads |
| `PUT` | `/threads/{id}` | Rename a thread |
| `GET` | `/threads/{id}/messages` | Full message history |
| `POST` | `/chat` | Send message → AI reply |
| `GET` | `/memory` | View stored user facts |

---

## Testing the API

**curl:**
```bash
curl https://lasya-chat-backend.onrender.com/health
curl -X POST https://lasya-chat-backend.onrender.com/threads
curl -X POST https://lasya-chat-backend.onrender.com/chat \
  -H "Content-Type: application/json" \
  -d '{"thread_id": 1, "message": "My name is Shivani"}'
```

**Windows PowerShell:**
```powershell
Invoke-RestMethod -Uri https://lasya-chat-backend.onrender.com/health
Invoke-RestMethod -Method Post -Uri https://lasya-chat-backend.onrender.com/threads `
  -ContentType "application/json" -Body '{}'
Invoke-RestMethod -Method Post -Uri https://lasya-chat-backend.onrender.com/chat `
  -ContentType "application/json" `
  -Body '{"thread_id": 1, "message": "My name is Shivani"}'
```

---

## Pre-Launch Checklist

```
[ ] OPENAI_API_KEY set (Render dashboard or local .env)
[ ] ALLOWED_ORIGINS set to frontend Render URL (backend service)
[ ] API_BASE set to backend Render URL (frontend service)
[ ] Both services show "Live" in Render dashboard
[ ] /health endpoint returns {"status": "ok"}
[ ] Swagger UI loads at /docs
[ ] Chat UI loads and accepts messages
```

---

## Common Issues

| Symptom | Cause | Fix |
|---|---|---|
| `RuntimeError: OPENAI_API_KEY is not configured` | Key not set | Add to Render Environment tab or local `.env` |
| Backend returns 502 on `/chat` | Invalid key or no billing | Verify key at platform.openai.com/api-keys |
| Frontend shows "Cannot reach the backend" | `API_BASE` not set | Set `API_BASE` to backend Render URL in frontend env vars |
| First request is very slow | Free tier cold start | Normal — wait 30s for service to wake up |
| Chat history disappears after deploy | SQLite ephemeral filesystem | Expected on free tier; use Postgres for persistence |
| `Activate.ps1` blocked on Windows | Execution policy | `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser` |
