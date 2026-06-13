# AI Chat Application

A production-quality mini AI chat application demonstrating a clean full-stack Python architecture.

| Layer | Technology |
|---|---|
| Frontend | Streamlit |
| Backend | FastAPI |
| Database | SQLite via SQLAlchemy ORM |
| AI | OpenAI `gpt-4o-mini` (swappable) |

---

## Features

- **Multi-thread chat** — create, rename, and switch between independent conversations
- **Full message history** — every message is persisted to SQLite and restored on revisit
- **Universal memory** — facts shared in any thread (e.g. your name) are remembered across all future threads automatically
- **Clean architecture** — Pydantic schemas, SQLAlchemy ORM, environment-based config, no hardcoded secrets

---

## Project Structure

```
lasya-api-llm/
├── app.py           # FastAPI backend — routes, LLM calls, memory logic
├── database.py      # SQLAlchemy models and session factory
├── main.py          # Streamlit frontend
├── requirements.txt # Pinned Python dependencies
├── .env.example     # Environment variable template (copy to .env)
├── .gitignore       # Excludes .env, *.db, venv, __pycache__, etc.
└── README.md
```

---

## Prerequisites

| Requirement | Minimum version | Check command |
|---|---|---|
| Python | 3.9+ (3.11 recommended) | `python --version` |
| pip | any | `pip --version` |
| Git | any | `git --version` |
| OpenAI API key | — | platform.openai.com/api-keys |

---

## Installation

### 1 · Clone the repository

```bash
# Linux / macOS / Windows (Git Bash or PowerShell)
git clone https://github.com/priyalasya9/lasya-api-llm.git
cd lasya-api-llm
git checkout claude/nifty-davinci-981uo7
```

### 2 · Create a virtual environment

```bash
# Linux / macOS
python3 -m venv venv
source venv/bin/activate

# Windows PowerShell
python -m venv venv
venv\Scripts\Activate.ps1
```

> **Windows tip:** if `Activate.ps1` is blocked, run this once:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

### 3 · Install dependencies

```bash
pip install -r requirements.txt
```

### 4 · Configure environment variables

```bash
# Linux / macOS
cp .env.example .env

# Windows PowerShell
copy .env.example .env
```

Open `.env` and set your OpenAI key:

```dotenv
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxx
```

See `.env.example` for all available options.

---

## Running the Application

You need **two terminals**, both with the virtual environment activated.

### Terminal 1 — FastAPI backend

```bash
uvicorn app:app --reload
```

Expected output:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

The SQLite database (`chats.db`) is created automatically on first startup. No migration step required.

### Terminal 2 — Streamlit frontend

```bash
streamlit run main.py
```

Expected output:
```
  Local URL: http://localhost:8501
```

Your browser opens automatically. If it does not, navigate to `http://localhost:8501`.

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | **Yes** | — | OpenAI secret key (`sk-proj-...`) |
| `LLM_MODEL` | No | `gpt-4o-mini` | Any OpenAI chat model |
| `DATABASE_URL` | No | `sqlite:///./chats.db` | SQLAlchemy connection string |
| `ALLOWED_ORIGINS` | No | `http://localhost:8501,...` | Comma-separated CORS origins |
| `API_BASE` | No | `http://localhost:8000` | Backend URL used by the frontend |

---

## API Reference

Interactive Swagger docs: **http://localhost:8000/docs**

| Method | Path | Body | Description |
|---|---|---|---|
| `GET` | `/health` | — | Liveness probe |
| `POST` | `/threads` | `{"title": "..."}` | Create a thread |
| `GET` | `/threads` | — | List all threads |
| `PUT` | `/threads/{id}` | `{"title": "..."}` | Rename a thread |
| `GET` | `/threads/{id}/messages` | — | Get thread history |
| `POST` | `/chat` | `{"thread_id": 1, "message": "..."}` | Chat with the AI |
| `GET` | `/memory` | — | View all stored user facts |

### Quick test with curl

```bash
# Health check
curl http://localhost:8000/health

# Create a thread
curl -X POST http://localhost:8000/threads

# Send a message
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"thread_id": 1, "message": "My name is Shivani"}'

# Prove universal memory in a new thread
curl -X POST http://localhost:8000/threads
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"thread_id": 2, "message": "What is my name?"}'
# → "Your name is Shivani."
```

### Quick test with Windows PowerShell

```powershell
# Health check
Invoke-RestMethod -Uri http://localhost:8000/health

# Create a thread
Invoke-RestMethod -Method Post -Uri http://localhost:8000/threads `
  -ContentType "application/json" -Body '{}'

# Send a message
Invoke-RestMethod -Method Post -Uri http://localhost:8000/chat `
  -ContentType "application/json" `
  -Body '{"thread_id": 1, "message": "My name is Shivani"}'

# Prove universal memory
Invoke-RestMethod -Method Post -Uri http://localhost:8000/threads `
  -ContentType "application/json" -Body '{}'
Invoke-RestMethod -Method Post -Uri http://localhost:8000/chat `
  -ContentType "application/json" `
  -Body '{"thread_id": 2, "message": "What is my name?"}'
```

---

## How Universal Memory Works

```
User sends message
      │
      ▼
 Save to DB (messages table)
      │
      ├──► [background] LLM extracts facts → saved to memory table
      │
      ▼
 Load full thread history
      │
      ▼
 Load all memory facts
      │
      ▼
 Build system prompt:
   "You are a helpful assistant.
    Known user facts:
    - User's name is Shivani
    - User is learning SQL"
      │
      ▼
 Call OpenAI → stream reply → save → return to frontend
```

Memory extraction is best-effort: if it fails, the main chat response is never blocked.

---

## Extending to Other LLM Providers

The LLM call is isolated in `app.py`. To swap providers:

**Groq** (OpenAI-compatible API):
```python
from openai import OpenAI
client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)
```

**Google Gemini**: install `google-generativeai` and wrap the `generate_content` call behind the same `build_openai_messages` helper.

Set `LLM_MODEL` in `.env` to switch models without touching any code.

---

## Deployment Checklist

```
[ ] .env file created from .env.example
[ ] OPENAI_API_KEY set to a valid key with billing enabled
[ ] .env is listed in .gitignore (it is — do not remove it)
[ ] chats.db is listed in .gitignore (it is — regenerated on startup)
[ ] Virtual environment activated in both terminals
[ ] pip install -r requirements.txt completed with no errors
[ ] uvicorn running on port 8000 (Terminal 1)
[ ] streamlit running on port 8501 (Terminal 2)
[ ] http://localhost:8000/health returns {"status": "ok"}
[ ] http://localhost:8501 opens the chat UI
```

---

## Common Issues

| Symptom | Cause | Fix |
|---|---|---|
| `RuntimeError: OPENAI_API_KEY is not set` | Missing `.env` or wrong key value | Copy `.env.example` → `.env`, paste your key |
| `Cannot reach the backend` in the UI | `uvicorn` not running | Start Terminal 1 with `uvicorn app:app --reload` |
| `openai.AuthenticationError` | Invalid API key | Verify key at platform.openai.com/api-keys |
| `openai.RateLimitError` | No billing on OpenAI account | Add payment at platform.openai.com/billing |
| `Activate.ps1 cannot be loaded` | Windows execution policy | `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser` |
| Port 8000 in use | Another process | `uvicorn app:app --reload --port 8001` + set `API_BASE=http://localhost:8001` in `.env` |
