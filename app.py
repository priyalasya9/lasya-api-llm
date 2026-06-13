"""
app.py — FastAPI backend for the AI Chat Application.

Routes
------
POST /threads                – create a new chat thread
GET  /threads                – list all threads (newest first)
PUT  /threads/{id}           – rename a thread
GET  /threads/{id}/messages  – fetch full message history for a thread
POST /chat                   – send a user message and receive an AI reply
GET  /memory                 – list all stored universal memory facts
GET  /health                 – liveness probe
"""

import json
import os
from datetime import datetime
from typing import List

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import ChatThread, Memory, Message, create_tables, get_db

load_dotenv()

# ---------------------------------------------------------------------------
# Startup validation — fail fast with a clear message
# ---------------------------------------------------------------------------

_api_key = os.getenv("OPENAI_API_KEY", "")
if not _api_key or _api_key == "your_key_here":
    raise RuntimeError(
        "OPENAI_API_KEY is not set. "
        "Copy .env.example to .env and add your OpenAI API key."
    )

# ---------------------------------------------------------------------------
# App bootstrap
# ---------------------------------------------------------------------------

# CORS origins — comma-separated list from env, defaults to localhost only.
# Set ALLOWED_ORIGINS=* in .env only if you understand the security implications.
_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:8501,http://127.0.0.1:8501")
ALLOWED_ORIGINS: List[str] = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app = FastAPI(title="AI Chat API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Content-Type"],
)

# Create DB tables on startup (idempotent — safe to call every time)
create_tables()

openai_client = OpenAI(api_key=_api_key)
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class ThreadCreate(BaseModel):
    title: str = "New Chat"


class ThreadUpdate(BaseModel):
    title: str


class ThreadOut(BaseModel):
    id: int
    title: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    id: int
    thread_id: int
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatRequest(BaseModel):
    thread_id: int
    message: str


class ChatResponse(BaseModel):
    reply: str
    thread_id: int


class MemoryOut(BaseModel):
    id: int
    fact: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Universal memory helpers
# ---------------------------------------------------------------------------

_MEMORY_EXTRACTION_PROMPT = """
You are a memory extraction assistant. Given a user message, extract any personal
facts or preferences the user revealed about themselves (name, job, hobbies, goals,
preferences, etc.).

Return ONLY a JSON array of short factual strings. If nothing notable is revealed,
return an empty array [].

Examples:
  User: "My name is Shivani and I love hiking"
  → ["User's name is Shivani", "User loves hiking"]

  User: "What is 2 + 2?"
  → []
"""


def extract_and_store_memory(user_message: str, db: Session) -> None:
    """
    Best-effort: ask the LLM to extract personal facts from the user message
    and persist any new ones to the Memory table.
    Failures are silently swallowed so they never block the main chat flow.
    """
    try:
        response = openai_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": _MEMORY_EXTRACTION_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0,
            max_tokens=200,
        )
        raw = response.choices[0].message.content.strip()
        facts: List[str] = json.loads(raw)
        for fact in facts:
            if fact.strip():
                db.add(Memory(fact=fact.strip()))
        db.commit()
    except Exception:
        pass


def build_memory_context(db: Session) -> str:
    """Return a formatted block of all stored user facts for the system prompt."""
    facts = db.query(Memory).order_by(Memory.created_at).all()
    if not facts:
        return ""
    lines = "\n".join(f"- {f.fact}" for f in facts)
    return f"\nKnown user facts:\n{lines}"


def build_openai_messages(thread_messages: List[Message], memory_context: str) -> list:
    system_content = "You are a helpful assistant."
    if memory_context:
        system_content += f"\n{memory_context}"

    payload: list = [{"role": "system", "content": system_content}]
    for msg in thread_messages:
        payload.append({"role": msg.role, "content": msg.content})
    return payload


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.post("/threads", response_model=ThreadOut, status_code=201)
def create_thread(body: ThreadCreate = ThreadCreate(), db: Session = Depends(get_db)):
    thread = ChatThread(title=body.title)
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return thread


@app.get("/threads", response_model=List[ThreadOut])
def list_threads(db: Session = Depends(get_db)):
    return db.query(ChatThread).order_by(ChatThread.created_at.desc()).all()


@app.put("/threads/{thread_id}", response_model=ThreadOut)
def rename_thread(thread_id: int, body: ThreadUpdate, db: Session = Depends(get_db)):
    thread = db.query(ChatThread).filter(ChatThread.id == thread_id).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    thread.title = body.title
    db.commit()
    db.refresh(thread)
    return thread


@app.get("/threads/{thread_id}/messages", response_model=List[MessageOut])
def get_thread_messages(thread_id: int, db: Session = Depends(get_db)):
    thread = db.query(ChatThread).filter(ChatThread.id == thread_id).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return (
        db.query(Message)
        .filter(Message.thread_id == thread_id)
        .order_by(Message.created_at)
        .all()
    )


@app.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, db: Session = Depends(get_db)):
    thread = db.query(ChatThread).filter(ChatThread.id == body.thread_id).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Persist user message
    db.add(Message(thread_id=body.thread_id, role="user", content=body.message))
    db.commit()

    # Auto-title the thread on its first message
    msg_count = db.query(Message).filter(Message.thread_id == body.thread_id).count()
    if msg_count == 1 and thread.title == "New Chat":
        thread.title = body.message[:60] + ("…" if len(body.message) > 60 else "")
        db.commit()

    # Extract memory facts asynchronously (best-effort, non-blocking)
    extract_and_store_memory(body.message, db)

    # Load full thread history to give the LLM complete context
    history = (
        db.query(Message)
        .filter(Message.thread_id == body.thread_id)
        .order_by(Message.created_at)
        .all()
    )

    openai_messages = build_openai_messages(history, build_memory_context(db))

    try:
        completion = openai_client.chat.completions.create(
            model=LLM_MODEL,
            messages=openai_messages,
            temperature=0.7,
        )
        reply_text = completion.choices[0].message.content.strip()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM error: {exc}") from exc

    # Persist assistant reply
    db.add(Message(thread_id=body.thread_id, role="assistant", content=reply_text))
    db.commit()

    return ChatResponse(reply=reply_text, thread_id=body.thread_id)


@app.get("/memory", response_model=List[MemoryOut])
def get_memory(db: Session = Depends(get_db)):
    return db.query(Memory).order_by(Memory.created_at.desc()).all()


@app.get("/health")
def health():
    return {"status": "ok"}
