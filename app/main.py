from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.models import InboundMessage, Message, RepliesResponse
from app.store import store

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")

app = FastAPI(title="SmartBubble", description="SMS demo for Solution Engineers")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


def _messages_context(session_id: str, messages: list[Message]) -> dict:
    return {
        "session_id": session_id,
        "messages": messages,
    }


@app.get("/", response_class=HTMLResponse)
async def landing(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "landing.html",
        {"title": "SmartBubble"},
    )


@app.post("/api/sessions/{session_id}/messages", response_model=Message)
async def send_message(session_id: str, payload: InboundMessage) -> Message:
    return await store.add_to_phone(session_id, payload.body, payload.from_)


@app.get("/api/sessions/{session_id}/replies", response_model=RepliesResponse)
async def get_replies(session_id: str, since: int = 0) -> RepliesResponse:
    replies, next_cursor = await store.list_replies_since(session_id, since)
    return RepliesResponse(messages=replies, next_cursor=next_cursor)


@app.get("/{session_id}", response_class=HTMLResponse)
async def chat_page(request: Request, session_id: str) -> HTMLResponse:
    messages = await store.list_all(session_id)
    return templates.TemplateResponse(
        request,
        "chat.html",
        _messages_context(session_id, messages),
    )


@app.get("/{session_id}/stream", response_class=HTMLResponse)
async def chat_stream(request: Request, session_id: str) -> HTMLResponse:
    messages = await store.list_all(session_id)
    return templates.TemplateResponse(
        request,
        "_messages.html",
        _messages_context(session_id, messages),
    )


@app.post("/{session_id}/reply", response_class=HTMLResponse)
async def chat_reply(
    request: Request,
    session_id: str,
    body: str = Form(...),
) -> HTMLResponse:
    await store.add_from_phone(session_id, body)
    messages = await store.list_all(session_id)
    return templates.TemplateResponse(
        request,
        "_messages.html",
        _messages_context(session_id, messages),
    )
