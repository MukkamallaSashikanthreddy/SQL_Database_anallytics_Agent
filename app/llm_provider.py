"""Gemini model construction with explicit timeout and no automatic SDK retries."""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.config import GOOGLE_API_KEY, GOOGLE_MODEL, GEMINI_TIMEOUT_SECONDS


class ProviderConfigurationError(RuntimeError):
    pass


def gemini_configuration_status() -> dict[str, Any]:
    return {
        "configured": bool(GOOGLE_API_KEY),
        "model": GOOGLE_MODEL,
        "timeout_seconds": GEMINI_TIMEOUT_SECONDS,
        "automatic_retries": 0,
    }


@lru_cache(maxsize=1)
def get_gemini_model() -> Any:
    if not GOOGLE_API_KEY:
        raise ProviderConfigurationError("GOOGLE_API_KEY is missing. Add it to your local .env file.")
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError as exc:
        raise ProviderConfigurationError("langchain-google-genai is not installed. Install requirements.txt.") from exc

    # Gemini 3 models use thinking_level instead of the deprecated thinking_budget.
    # low is used to reduce latency and token cost for SQL generation.
    return ChatGoogleGenerativeAI(
        model=GOOGLE_MODEL,
        api_key=GOOGLE_API_KEY,
        timeout=GEMINI_TIMEOUT_SECONDS,
        max_retries=0,
        thinking_level="low",
    )


def response_text(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        fragments = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                fragments.append(str(item.get("text", "")))
            else:
                fragments.append(str(item))
        return "\n".join(fragments).strip()
    return str(content).strip()
