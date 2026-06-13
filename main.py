"""
main.py — Streamlit frontend for the AI Chat Application.

Layout
------
Sidebar : New Chat button + scrollable thread list + rename widget + memory inspector
Main    : Chat message history + sticky input box
"""

from __future__ import annotations  # enables list[dict] syntax on Python 3.9

import os

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Config — read from environment so the same image works in any environment
# ---------------------------------------------------------------------------

API_BASE = os.getenv("API_BASE", "http://localhost:8000")

st.set_page_config(
    page_title="AI Chat",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Session-state initialisation (runs once per browser session)
# ---------------------------------------------------------------------------

if "active_thread_id" not in st.session_state:
    st.session_state.active_thread_id: int | None = None

if "active_thread_title" not in st.session_state:
    st.session_state.active_thread_title: str = ""

if "messages" not in st.session_state:
    st.session_state.messages: list[dict] = []

# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

_TIMEOUT_SHORT = 10   # seconds — for read-only / rename calls
_TIMEOUT_CHAT  = 60   # seconds — LLM calls can be slow


def api_get(path: str) -> list | dict | None:
    try:
        r = requests.get(f"{API_BASE}{path}", timeout=_TIMEOUT_SHORT)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error(
            "⚠️ Cannot reach the backend. "
            "Make sure `uvicorn app:app --reload` is running on port 8000."
        )
        return None
    except requests.exceptions.HTTPError as exc:
        st.error(f"API error {exc.response.status_code}: {exc.response.text}")
        return None


def api_post(path: str, payload: dict) -> dict | None:
    try:
        r = requests.post(f"{API_BASE}{path}", json=payload, timeout=_TIMEOUT_CHAT)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error(
            "⚠️ Cannot reach the backend. "
            "Make sure `uvicorn app:app --reload` is running on port 8000."
        )
        return None
    except requests.exceptions.HTTPError as exc:
        st.error(f"API error {exc.response.status_code}: {exc.response.text}")
        return None


def api_put(path: str, payload: dict) -> dict | None:
    try:
        r = requests.put(f"{API_BASE}{path}", json=payload, timeout=_TIMEOUT_SHORT)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("⚠️ Cannot reach the backend.")
        return None
    except requests.exceptions.HTTPError as exc:
        st.error(f"Rename failed — {exc.response.status_code}: {exc.response.text}")
        return None


# ---------------------------------------------------------------------------
# Domain helpers
# ---------------------------------------------------------------------------


def fetch_threads() -> list[dict]:
    data = api_get("/threads")
    return data if isinstance(data, list) else []


def fetch_messages(thread_id: int) -> list[dict]:
    data = api_get(f"/threads/{thread_id}/messages")
    return data if isinstance(data, list) else []


def create_thread() -> dict | None:
    return api_post("/threads", {"title": "New Chat"})


def send_message(thread_id: int, message: str) -> dict | None:
    return api_post("/chat", {"thread_id": thread_id, "message": message})


# ---------------------------------------------------------------------------
# State actions
# ---------------------------------------------------------------------------


def select_thread(thread_id: int, title: str) -> None:
    st.session_state.active_thread_id = thread_id
    st.session_state.active_thread_title = title
    st.session_state.messages = fetch_messages(thread_id)


def handle_new_chat() -> None:
    thread = create_thread()
    if thread:
        select_thread(thread["id"], thread["title"])


def handle_send(user_input: str) -> None:
    if not user_input.strip():
        return

    thread_id = st.session_state.active_thread_id
    if not thread_id:
        st.warning("Please select or create a chat first.")
        return

    # Optimistically show the user message before waiting for the LLM
    st.session_state.messages.append({"role": "user", "content": user_input})

    with st.spinner("Thinking…"):
        result = send_message(thread_id, user_input)

    if result:
        st.session_state.messages.append(
            {"role": "assistant", "content": result["reply"]}
        )
        # Rerun so the sidebar reflects any auto-title change
        st.rerun()


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("🤖 AI Chat")
    st.divider()

    if st.button("➕  New Chat", use_container_width=True, type="primary"):
        handle_new_chat()

    st.subheader("Your Chats")

    threads = fetch_threads()

    if not threads:
        st.caption("No chats yet. Hit **New Chat** to start.")
    else:
        for thread in threads:
            is_active = thread["id"] == st.session_state.active_thread_id
            label = f"{'▶ ' if is_active else ''}{thread['title']}"
            if st.button(label, key=f"thread_{thread['id']}", use_container_width=True):
                select_thread(thread["id"], thread["title"])

    # Rename widget — only visible when a thread is active
    if st.session_state.active_thread_id:
        st.divider()
        st.subheader("Rename Chat")
        new_title = st.text_input(
            "New name",
            value=st.session_state.active_thread_title,
            key="rename_input",
            label_visibility="collapsed",
        )
        if st.button("Rename", use_container_width=True):
            updated = api_put(
                f"/threads/{st.session_state.active_thread_id}",
                {"title": new_title},
            )
            if updated:
                st.session_state.active_thread_title = updated["title"]
                st.success("Renamed!")
                st.rerun()

    # Memory inspector
    with st.expander("🧠 Universal Memory"):
        memory = api_get("/memory")
        if memory:
            for item in memory:
                st.markdown(f"- {item['fact']}")
        else:
            st.caption("No facts stored yet.")

# ---------------------------------------------------------------------------
# Main chat area
# ---------------------------------------------------------------------------

if not st.session_state.active_thread_id:
    st.markdown(
        """
        <div style="display:flex;flex-direction:column;align-items:center;
                    justify-content:center;height:70vh;text-align:center;">
            <h1>🤖 AI Chat</h1>
            <p style="font-size:1.1rem;color:#888;">
                Select a chat from the sidebar or create a new one to get started.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    col_title, _ = st.columns([4, 1])
    with col_title:
        st.subheader(st.session_state.active_thread_title or "Chat")

    with st.container():
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    user_input = st.chat_input("Type a message…")
    if user_input:
        handle_send(user_input)
