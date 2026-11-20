"""Load .env once for every lib module (host secrets arrive as env vars instead)."""
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
