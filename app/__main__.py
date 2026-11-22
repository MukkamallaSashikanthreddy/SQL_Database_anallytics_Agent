"""Optional module entry point."""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
raise SystemExit(subprocess.call([sys.executable, "-m", "streamlit", "run", str(ROOT / "app.py")], cwd=ROOT))
