import os
import re

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = (os.getenv("BOT_TOKEN") or "").strip()
WEBAPP_URL = (os.getenv("WEBAPP_URL") or "").strip()
DATABASE_URL = (os.getenv("DATABASE_URL") or "").strip()
POLL_INTERVAL = max(30, int(os.getenv("POLL_INTERVAL") or 60))

MAX_QUERIES = 20       # per user (also enforced by the database)
MAX_QUERY_LEN = 80
SCAN_LIMIT = 20        # ads taken from the first Kufar page per scan
MAX_SEND_PER_CYCLE = 10


def validate() -> None:
    errors = []
    if not re.fullmatch(r"\d+:[\w-]{30,}", BOT_TOKEN):
        errors.append("BOT_TOKEN is missing or malformed (check bot/.env)")
    if not DATABASE_URL.startswith(("postgresql://", "postgres://")):
        errors.append("DATABASE_URL is missing (Supabase -> Connect -> Session pooler)")
    if WEBAPP_URL and not WEBAPP_URL.startswith("https://"):
        errors.append("WEBAPP_URL must start with https://")
    if errors:
        raise SystemExit("Config error:\n - " + "\n - ".join(errors))
