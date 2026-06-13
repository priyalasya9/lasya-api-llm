# AI Chat Application

A production-quality mini AI chat app built with **Streamlit**, **FastAPI**, **SQLite**, and the **OpenAI API**.

## Features

| Feature | Details |
|---|---|
| Chat with an LLM | Sends messages to OpenAI and displays replies |
| Multiple chat threads | Create, rename, and switch between independent conversations |
| Full message history | Every message persisted to SQLite; restored on revisit |
| Universal memory | Facts shared in any thread are remembered across **all** future threads |

## Project Structure

```
project/
├── main.py          # Streamlit frontend
├── app.py           # FastAPI backend
├── database.py      # SQLAlchemy models & session factory
├── requirements.txt
├── .env.example
├── chats.db         # auto-created on first run
└── README.md
```

## Quick Start

### 1. Clone & install

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and set your OPENAI_API_KEY
```

### 3. Run the backend

```bash
uvicorn app:app --reload
```

The API is now live at `http://localhost:8000`.  
Interactive docs: `http://localhost:8000/docs`

### 4. Run the frontend

In a **second terminal**:

```bash
streamlit run main.py
```

Open `http://localhost:8501` in your browser.

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/threads` | Create a new chat thread |
| `GET` | `/threads` | List all threads (newest first) |
| `PUT` | `/threads/{id}` | Rename a thread |
| `GET` | `/threads/{id}/messages` | Fetch message history |
| `POST` | `/chat` | Send a message; returns AI reply |
| `GET` | `/memory` | List all stored user facts |
| `GET` | `/health` | Health check |

### Example: start a chat

```bash
# 1. Create a thread
curl -X POST http://localhost:8000/threads
# → {"id": 1, "title": "New Chat", "created_at": "..."}

# 2. Send a message
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"thread_id": 1, "message": "My name is Shivani"}'
# → {"reply": "Nice to meet you, Shivani! ...", "thread_id": 1}

# 3. In a new thread, ask about the memory
curl -X POST http://localhost:8000/threads
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"thread_id": 2, "message": "What is my name?"}'
# → {"reply": "Your name is Shivani.", "thread_id": 2}
```

## Architecture Notes

### Universal Memory

Before every LLM call, the backend:
1. Queries all `Memory` rows from SQLite.
2. Injects them into the system prompt as a "Known user facts" block.

After every user message, a lightweight LLM call extracts any new personal facts and stores them in the `Memory` table. This is best-effort and never blocks the main chat response.

### Extending to other LLM providers

The OpenAI client is instantiated in `app.py`. To swap providers:

- **Groq** — Groq exposes an OpenAI-compatible REST API; just change `base_url` and `api_key`.
- **Gemini** — Use the `google-generativeai` SDK and wrap it behind the same `build_openai_messages` helper.
- Set `LLM_MODEL` in `.env` to switch models without touching code.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | — | OpenAI secret key |
| `LLM_MODEL` | No | `gpt-4o-mini` | Model identifier |
| `DATABASE_URL` | No | `sqlite:///./chats.db` | SQLAlchemy DB URL |
