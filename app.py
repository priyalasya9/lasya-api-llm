"""
app.py — FastAPI backend for the AI Chat Application.

Routes
------
POST /threads              – create a new chat thread
GET  /threads              – list all threads
PUT  /threads/{id}         – rename a thread
GET  /threads/{id}/messages – fetch message history for a thread
POST /chat                 – send a message and get an AI reply
GET  /memory               – list all stored universal memory facts
"""

import os
from datetime import datetime
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import ChatThread, Memory, Message, create_tables, get_db

load_dotenv()

# ---------------------------------------------------------------------------
# App bootstrap
# ---------------------------------------------------------------------------

app = FastAPI(title="AI Chat API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

create_tables()

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
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
# Helper: universal memory
# ---------------------------------------------------------------------------

MEMORY_EXTRACTION_PROMPT = """
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
    """Ask the LLM to extract facts from the user message and persist them."""
    try:
        response = openai_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": MEMORY_EXTRACTION_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0,
            max_tokens=200,
        )
        import json

        raw = response.choices[0].message.content.strip()
        facts: List[str] = json.loads(raw)
        for fact in facts:
            if fact.strip():
                db.add(Memory(fact=fact.strip()))
        db.commit()
    except Exception:
        # Memory extraction is best-effort; never block the main chat flow.
        pass


def build_memory_context(db: Session) -> str:
    """Return a formatted string of all known user facts for the system prompt."""
    facts = db.query(Memory).order_by(Memory.created_at).all()
    if not facts:
        return ""
    lines = "\n".join(f"- {f.fact}" for f in facts)
    return f"\nKnown user facts:\n{lines}"


# ---------------------------------------------------------------------------
# Helper: build messages payload for OpenAI
# ---------------------------------------------------------------------------


def build_openai_messages(thread_messages: List[Message], memory_context: str) -> list:
    system_content = "You are a helpful assistant."
    if memory_context:
        system_content += f"\n{memory_context}"

    payload = [{"role": "system", "content": system_content}]
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
    # Validate thread
    thread = db.query(ChatThread).filter(ChatThread.id == body.thread_id).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Persist user message
    user_msg = Message(thread_id=body.thread_id, role="user", content=body.message)
    db.add(user_msg)
    db.commit()

    # Auto-title the thread on the first message (cosmetic quality-of-life)
    msg_count = db.query(Message).filter(Message.thread_id == body.thread_id).count()
    if msg_count == 1 and thread.title == "New Chat":
        thread.title = body.message[:60] + ("…" if len(body.message) > 60 else "")
        db.commit()

    # Extract and store any new memory facts (best-effort, non-blocking)
    extract_and_store_memory(body.message, db)

    # Load full thread history (including the message we just saved)
    history = (
        db.query(Message)
        .filter(Message.thread_id == body.thread_id)
        .order_by(Message.created_at)
        .all()
    )

    # Load universal memory
    memory_context = build_memory_context(db)

    # Build OpenAI payload and call the API
    openai_messages = build_openai_messages(history, memory_context)
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
    assistant_msg = Message(thread_id=body.thread_id, role="assistant", content=reply_text)
    db.add(assistant_msg)
    db.commit()

    return ChatResponse(reply=reply_text, thread_id=body.thread_id)


@app.get("/memory", response_model=List[MemoryOut])
def get_memory(db: Session = Depends(get_db)):
    return db.query(Memory).order_by(Memory.created_at.desc()).all()


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health")
def health():
    return {"status": "ok"}
