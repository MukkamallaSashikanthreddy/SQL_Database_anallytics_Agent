"""Application settings loaded from environment variables."""
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env", override=True)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()
GOOGLE_MODEL = os.getenv("GOOGLE_MODEL", "gemini-3.5-flash-lite").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///database/analytics.db").strip()
MAX_SQL_RETRIES = min(max(int(os.getenv("MAX_SQL_RETRIES", "3")), 0), 3)
MAX_RESULT_ROWS = min(max(int(os.getenv("MAX_RESULT_ROWS", "1000")), 1), 1000)
GEMINI_TIMEOUT_SECONDS = 30
LANGGRAPH_RECURSION_LIMIT = 24
NEMO_GUARDRAILS_CONFIG = os.getenv("NEMO_GUARDRAILS_CONFIG", "config/guardrails").strip()
NEMO_LIVE_INFERENCE = os.getenv("NEMO_LIVE_INFERENCE", "false").lower() == "true"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

ALLOWED_TABLES = {"customers", "orders", "sales"}


def database_path() -> Path:
    """Return the resolved path for the configured SQLite URL."""
    prefix = "sqlite:///"
    if not DATABASE_URL.startswith(prefix):
        raise ValueError("This portfolio build supports a SQLite DATABASE_URL only.")
    raw = DATABASE_URL[len(prefix):]
    path = Path(raw)
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()
