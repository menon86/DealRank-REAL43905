"""Read-only, tool-grounded chat assistant.

  POST /chat              SSE stream: delta / tool / fallback / done events
  GET  /chat/suggestions  preset questions (+ whether the LLM is configured)
  POST /chat/preset       deterministic, LLM-free answer to a preset question

The model never computes or invents figures: it can only call the read-only
tools in app/api/chat_tools.py, which call the deterministic engine. When the
provider is rate-limited or down, /chat emits a `fallback` event and the UI
switches to the preset endpoint. There are no write tools in this version.
"""

from __future__ import annotations

import json
import math
import uuid
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from decimal import Decimal
from typing import Literal

import openai
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.api.analysis_schemas import WeightsIn
from app.api.chat_loop import LLM, REQUEST_TIMEOUT_SECONDS, stream_chat
from app.api.chat_presets import PRESET_BY_ID, PRESETS, answer_preset
from app.api.chat_tools import MAX_DEALS, ToolContext, UiContext
from app.config import Settings, get_settings
from app.db import SessionLocal, get_db
from app.services.rate_limit import chat_limiter

router = APIRouter(prefix="/chat", tags=["chat"])

MAX_MESSAGE_CHARS = 2000
MAX_HISTORY_MESSAGES = 20


class ChatMessage(BaseModel):
    # Clients may send only user/assistant turns: system and tool roles would
    # let a caller rewrite the instructions or forge tool results.
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)


class RankingContext(BaseModel):
    dscr_minimum: Decimal | None = Field(default=None, ge=0, le=5)
    treasury_yield: Decimal | None = Field(default=None, ge=0, le=1)
    hurdle_rate: Decimal | None = Field(default=None, ge=-1, le=1)
    weights: WeightsIn | None = None


class ChatContext(BaseModel):
    selected_deal_ids: list[uuid.UUID] = Field(default_factory=list, max_length=MAX_DEALS)
    ranking: RankingContext | None = None


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=MAX_HISTORY_MESSAGES)
    context: ChatContext | None = None

    @model_validator(mode="after")
    def _ends_with_user(self) -> ChatRequest:
        if self.messages[-1].role != "user":
            raise ValueError("the last message must be from the user")
        return self


class PresetRequest(BaseModel):
    preset_id: str
    context: ChatContext | None = None


class PresetOut(BaseModel):
    id: str
    question: str


class SuggestionsOut(BaseModel):
    llm_available: bool
    suggestions: list[PresetOut]


class PresetAnswerOut(BaseModel):
    id: str
    question: str
    answer: str


def get_llm(settings: Settings = Depends(get_settings)) -> LLM | None:
    """None when no key is configured. Overridden in tests; no network happens here."""
    if not settings.llm_configured:
        return None
    client = openai.OpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY.get_secret_value(),
        timeout=REQUEST_TIMEOUT_SECONDS,
        max_retries=0,  # the loop owns the single retry
    )
    return LLM(client=client, model=settings.LLM_MODEL, max_tokens=settings.LLM_MAX_TOKENS)


@contextmanager
def _session_scope() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_session_factory():
    """A streaming response outlives a request-scoped session, so the loop
    opens (and closes) its own per tool call."""
    return _session_scope


def client_key(request: Request) -> str:
    """Rate-limit key. Behind a proxy (Render) the socket peer is the proxy, so use the
    right-most X-Forwarded-For entry, the one our own proxy appended; left-most entries
    are client-supplied and spoofable."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def _ui_context(context: ChatContext | None) -> UiContext:
    ranking = context.ranking if context else None
    return UiContext(
        selected_deal_ids=tuple(context.selected_deal_ids) if context else (),
        dscr_minimum=ranking.dscr_minimum if ranking else None,
        treasury_yield=ranking.treasury_yield if ranking else None,
        weights=ranking.weights if ranking else None,
        hurdle_rate=ranking.hurdle_rate if ranking else None,
    )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


@router.post("")
def chat(
    payload: ChatRequest,
    request: Request,
    llm: LLM | None = Depends(get_llm),
    session_factory=Depends(get_session_factory),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    if llm is None:
        raise HTTPException(
            status_code=503,
            detail="The chat assistant is not configured. Use the preset questions.",
        )
    retry_after = chat_limiter.check(client_key(request), settings.CHAT_RATE_LIMIT_PER_MIN)
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail="Too many chat requests. Wait a moment or use the preset questions.",
            headers={"Retry-After": str(math.ceil(retry_after))},
        )

    history = [{"role": m.role, "content": m.content} for m in payload.messages]
    ui = _ui_context(payload.context)

    def events() -> Generator[str, None, None]:
        for event, data in stream_chat(llm, history, ui, session_factory):
            yield _sse(event, data)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/suggestions", response_model=SuggestionsOut)
def suggestions(settings: Settings = Depends(get_settings)) -> SuggestionsOut:
    return SuggestionsOut(
        llm_available=settings.llm_configured,
        suggestions=[PresetOut(id=p.id, question=p.question) for p in PRESETS],
    )


@router.post("/preset", response_model=PresetAnswerOut)
def preset(payload: PresetRequest, db: Session = Depends(get_db)) -> PresetAnswerOut:
    chosen = PRESET_BY_ID.get(payload.preset_id)
    if chosen is None:
        raise HTTPException(status_code=404, detail=f"Unknown preset '{payload.preset_id}'")
    answer = answer_preset(ToolContext.bind(_ui_context(payload.context), db), chosen.id)
    return PresetAnswerOut(id=chosen.id, question=chosen.question, answer=answer)
