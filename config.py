import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if present (local dev convenience)
load_dotenv(Path(__file__).parent / ".env")

# ── Prowlarr ──────────────────────────────────────────────────────────────────
PROWLARR_URL: str = os.getenv("PROWLARR_URL", "http://localhost:9696")
PROWLARR_API_KEY: str = os.getenv("PROWLARR_API_KEY", "")

# ── Auth ──────────────────────────────────────────────────────────────────────
# Set a strong random string in your environment / docker-compose
BEARER_TOKEN: str = os.getenv("BEARER_TOKEN", "changeme-secret-token")

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
CONFIG_DIR = BASE_DIR / "config"
MODELS_DIR = BASE_DIR / "models"
DB_PATH = CONFIG_DIR / "preferences.db"

CONFIG_DIR.mkdir(exist_ok=True)
MODELS_DIR.mkdir(exist_ok=True)

# ── AI Model ──────────────────────────────────────────────────────────────────
# Place your Phi-3.5-mini-instruct GGUF file in /models and set this name.
MODEL_FILENAME: str = os.getenv(
    "MODEL_FILENAME", "Phi-3.5-mini-instruct-Q4_K_M.gguf"
)
MODEL_PATH: str = str(MODELS_DIR / MODEL_FILENAME)

# llama-cpp context / thread settings
N_CTX: int = int(os.getenv("N_CTX", "4096"))
N_THREADS: int = int(os.getenv("N_THREADS", "4"))

# ── Scoring ───────────────────────────────────────────────────────────────────
# How many times a group must be chosen before a regex rule is auto-generated
REGEX_RULE_THRESHOLD: int = int(os.getenv("REGEX_RULE_THRESHOLD", "5"))

# 0.0 = pure exploitation (always top-scored), 1.0 = pure exploration (random)
EXPLORATION_FACTOR: float = float(os.getenv("EXPLORATION_FACTOR", "0.1"))
