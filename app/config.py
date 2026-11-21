"""Central configuration for the SQL analytics agent."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

DATABASE_PATH = Path(
    os.getenv("DATABASE_PATH", str(PROJECT_ROOT / "database" / "analytics.db"))
).expanduser().resolve()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
MAX_SQL_ATTEMPTS = int(os.getenv("MAX_SQL_ATTEMPTS", "3"))
MAX_RESULT_ROWS = int(os.getenv("MAX_RESULT_ROWS", "1000"))
SQLITE_QUERY_TIMEOUT_SECONDS = int(os.getenv("SQLITE_QUERY_TIMEOUT_SECONDS", "15"))

ALLOWED_TABLES = {
    "customers",
    "products",
    "orders",
    "order_items",
}
