"""Credential-safe Gemini connectivity diagnostic."""
from __future__ import annotations

import sys

from app.llm_provider import gemini_configuration_status, get_gemini_model, response_text


def main() -> int:
    status = gemini_configuration_status()
    print(f"Gemini model configured: {status['model']}")
    if not status["configured"]:
        print("GOOGLE_API_KEY is missing. Add it to .env and retry.")
        return 2
    try:
        model = get_gemini_model()
        answer = response_text(model.invoke("Return only this text: GEMINI_CONNECTION_OK"))
        print(f"Gemini response: {answer[:200]}")
        return 0 if "GEMINI_CONNECTION_OK" in answer else 1
    except Exception as exc:
        # Deliberately avoid printing exception text that may include request metadata.
        print(f"Gemini request failed: {type(exc).__name__}")
        print("Check model availability, API key permissions, network access, and free-tier quota.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
