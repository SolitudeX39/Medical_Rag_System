import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent

_API_KEYS = (
    "GOOGLE_API_KEY",
    "GEMINI_API_KEY",
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
)


def load_project_env() -> None:
    load_dotenv(ROOT / ".env", override=True)
    for key in _API_KEYS:
        value = os.getenv(key)
        if value is not None:
            os.environ[key] = value.strip()
    google_key = os.getenv("GOOGLE_API_KEY")
    if google_key and not os.getenv("GEMINI_API_KEY"):
        os.environ["GEMINI_API_KEY"] = google_key
