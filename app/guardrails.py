"""Deterministic input guardrails plus optional NeMo self-check input rail."""
from __future__ import annotations

import html
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from urllib.parse import unquote
from typing import Any

from app.config import NEMO_GUARDRAILS_CONFIG, NEMO_LIVE_INFERENCE, OPENAI_API_KEY, PROJECT_ROOT


class InputBlockedError(ValueError):
    """Raised when a user request is considered unsafe for SQL generation."""


# Rules deliberately target clear destructive / injection patterns rather than ordinary analytics words.
BLOCK_PATTERNS = [
    re.compile(r"\b(drop|delete|truncate|alter|update|insert|replace)\s+(table|from|into|database|\w+)\b", re.I),
    re.compile(r"\b(create|attach|detach)\s+(table|database|trigger|view)\b", re.I),
    re.compile(r"\b(or|and)\s+['\"]?\d+['\"]?\s*=\s*['\"]?\d+['\"]?", re.I),
    re.compile(r"(?:--|/\*|\*/|;\s*(?:drop|delete|update|insert|alter)\b)", re.I),
    re.compile(r"<\s*script\b|javascript\s*:", re.I),
    re.compile(r"\b(ignore|disregard|override)\s+(all\s+)?(previous|prior|system|developer)\s+instructions\b", re.I),
    re.compile(r"\b(reveal|print|show)\s+(?:(?:the|my|our)\s+)?(?:(?:hidden|private|confidential)\s+)?(system prompt|developer prompt|api key|secret key|credentials)\b", re.I),
]


def normalize_user_input(value: str) -> str:
    text = html.unescape(value)
    # Decode a small number of times to catch URL-encoded guardrail bypass attempts.
    for _ in range(2):
        decoded = unquote(text)
        if decoded == text:
            break
        text = decoded
    return unicodedata.normalize("NFKC", text)


def check_deterministic_input(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InputBlockedError("Enter a business analytics question.")
    if len(value) > 4_000:
        raise InputBlockedError("The question is too long. Please keep it under 4,000 characters.")
    normalized = normalize_user_input(value).strip()
    for pattern in BLOCK_PATTERNS:
        if pattern.search(normalized):
            raise InputBlockedError("The request was blocked by the input safety filter. Ask a read-only business analytics question instead.")
    return normalized


@lru_cache(maxsize=1)
def _build_nemo_rails() -> Any:
    """Initialize NeMo lazily; this is only used when NEMO_LIVE_INFERENCE=true."""
    if not OPENAI_API_KEY:
        raise RuntimeError("NEMO_LIVE_INFERENCE is enabled, but OPENAI_API_KEY is not configured.")
    try:
        from nemoguardrails import LLMRails, RailsConfig
    except ImportError as exc:
        raise RuntimeError("NeMo Guardrails is not installed. Install requirements.txt before enabling live NeMo inference.") from exc
    try:
        from nemoguardrails import Guardrails
    except ImportError:
        Guardrails = None
    config_path = (PROJECT_ROOT / NEMO_GUARDRAILS_CONFIG).resolve()
    if not config_path.is_dir():
        raise RuntimeError(f"NeMo Guardrails configuration folder not found: {config_path}")
    config = RailsConfig.from_path(str(config_path))
    # The Guardrails facade is preferred by current releases; LLMRails remains
    # a compatibility fallback for the 0.24.x API.
    if Guardrails is not None:
        try:
            return Guardrails(config)
        except Exception:
            pass
    return LLMRails(config)


def check_nemo_input(value: str) -> None:
    """Run the optional NeMo self-check input rail; fail closed on errors."""
    rails = _build_nemo_rails()
    # NeMo's built-in `self check input` flow blocks unsafe inputs by returning its refusal.
    messages = [{"role": "user", "content": value}]
    # check() runs only configured rails; it does not generate a normal assistant answer.
    if hasattr(rails, "check"):
        # Current NeMo Guardrails returns a RailOutcome whose documented decision
        # property is `is_blocked`. Keep compatibility with wrappers that expose
        # a string status or a dictionary result.
        result = rails.check(messages=messages)
        if hasattr(result, "is_blocked"):
            if bool(result.is_blocked):
                raise InputBlockedError("NeMo Guardrails blocked this request.")
            return
        if isinstance(result, dict) and "is_blocked" in result:
            if bool(result["is_blocked"]):
                raise InputBlockedError("NeMo Guardrails blocked this request.")
            return
        status = getattr(getattr(result, "status", None), "value", getattr(result, "status", None))
        if isinstance(result, dict):
            status = result.get("status", status)
        if str(status).upper() == "BLOCKED":
            raise InputBlockedError("NeMo Guardrails blocked this request.")
        if str(status).upper() in {"PASSED", "MODIFIED", "ALLOWED"}:
            return
        raise RuntimeError("NeMo Guardrails returned an unknown result.")

    # Compatibility path for older LLMRails versions: run input rails only,
    # not the full dialog/generation pipeline.
    result = rails.generate(messages=messages, options={"rails": ["input"]})
    content = str(result.get("content", "")).strip().lower() if isinstance(result, dict) else str(result).lower()
    refusal_markers = ("i'm sorry, i can't respond", "i cannot help with that request", "i can't help with that request", "request was blocked")
    if any(marker in content for marker in refusal_markers):
        raise InputBlockedError("NeMo Guardrails blocked this request.")


def check_user_input(value: str) -> str:
    """Always run deterministic checks; optionally run NeMo live inference."""
    normalized = check_deterministic_input(value)
    if NEMO_LIVE_INFERENCE:
        try:
            check_nemo_input(normalized)
        except InputBlockedError:
            raise
        except Exception as exc:
            # Fail closed when explicitly enabled: don't send unreviewed input to Gemini.
            raise InputBlockedError(f"NeMo Guardrails could not verify this request. Processing stopped ({type(exc).__name__}).") from exc
    return normalized
