"""Carrega e valida as configuracoes a partir do arquivo .env."""

import os
import sys

from dotenv import load_dotenv

load_dotenv()


def _req(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        print(f"[ERRO] Variavel obrigatoria ausente no .env: {name}")
        sys.exit(1)
    return value


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


# --- Credenciais MTProto (my.telegram.org) ---
API_ID = int(_req("TG_API_ID"))
API_HASH = _req("TG_API_HASH")

# --- Bot notificador (@BotFather) ---
BOT_TOKEN = _req("TG_BOT_TOKEN")
BOT_ID = int(BOT_TOKEN.split(":")[0])  # id numerico do bot = prefixo do token
OWNER_ID = int(_req("TG_OWNER_ID"))

# --- Caminhos persistentes ---
DATA_DIR = os.getenv("DATA_DIR", "data")
SESSION_PATH = os.path.join(DATA_DIR, "user")
DB_PATH = os.path.join(DATA_DIR, "alerts.db")

# --- Comportamento ---
FUZZY_THRESHOLD = _int("FUZZY_THRESHOLD", 88)
DEDUPE_TTL_HOURS = _int("DEDUPE_TTL_HOURS", 6)
MAX_ALERTS_PER_HOUR = _int("MAX_ALERTS_PER_HOUR", 12)
SNIPPET_CHARS = _int("SNIPPET_CHARS", 400)

os.makedirs(DATA_DIR, exist_ok=True)
