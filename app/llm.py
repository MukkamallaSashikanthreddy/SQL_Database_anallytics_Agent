"""Optional Gemini provider integration."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.config import GEMINI_API_KEY, GEMINI_MODEL


def gemini_is_configured() -> bool:
    return bool(GEMINI_API_KEY)


@lru_cache(maxsize=1)
def get_gemini_model() -> Any:
    """Create the Gemini chat model lazily so demo mode needs no API key."""
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not configured. Add it to your .env file or use Demo mode.")

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError as exc:
        raise RuntimeError(
            "Gemini integration is not installed. Run `pip install -r requirements.txt`."
        ) from exc

    return ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        google_api_key=GEMINI_API_KEY,
        temperature=0,
        max_retries=2,
    )


def invoke_text(model: Any, prompt: str) -> str:
    """Invoke a LangChain-compatible model and normalize its response to text."""
    response = model.invoke(prompt)
    content = getattr(response, "content", response)
    if isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                text_parts.append(str(part.get("text", "")))
            else:
                text_parts.append(str(part))
        return "\n".join(text_parts).strip()
    return str(content).strip()
