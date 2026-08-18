"""Application configuration from environment (.env optional)."""
import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # dotenv optional; ignore if not installed
    pass


def _float_env(name: str, default: float) -> float:
    v = os.getenv(name)
    if v is None or v.strip() == "":
        return default
    try:
        return float(v)
    except ValueError:
        return default


def _int_env(name: str, default: int) -> int:
    v = os.getenv(name)
    if v is None or v.strip() == "":
        return default
    try:
        return int(v)
    except ValueError:
        return default


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

DEDUP_THRESHOLD = _float_env("DEDUP_THRESHOLD", 0.82)
SIMILARITY_THRESHOLD = _float_env("SIMILARITY_THRESHOLD", 0.85)

SOURCE_GOOGLE_NEWS = bool(_int_env("SOURCE_GOOGLE_NEWS", 1))
SOURCE_GDELT = bool(_int_env("SOURCE_GDELT", 1))
SOURCE_HACKER_NEWS = bool(_int_env("SOURCE_HACKER_NEWS", 1))
SOURCE_COINGECKO = bool(_int_env("SOURCE_COINGECKO", 0))

# Database path (project-local single file)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "finsignal.db")
SNAPSHOTS_DIR = os.path.join(BASE_DIR, "data", "snapshots")
SIMULATED_DIR = os.path.join(BASE_DIR, "data", "simulated")
