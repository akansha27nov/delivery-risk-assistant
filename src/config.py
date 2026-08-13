# src/config.py
import os
from dotenv import load_dotenv

# Automatically load .env file
load_dotenv()

# ==========================================================
# 🔑 API Credentials
# ==========================================================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ==========================================================
# 🤖 Model Configurations
# ==========================================================
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_DIM = 1536
# ===========================================================
# 🌲 Vector Store Settings
# ===========================================================
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX", "delivery-risk-assistant")

# ===========================================================
# ⚙️ Pipeline Thresholds & Parameters
# ===========================================================
MAX_CHUNK_CHARS = 600
MIN_EVIDENCE_CHUNKS = 2
DEFAULT_TOP_K = 5      
FINAL_TOP_N = 8         # The final number of chunks to keep after reranking

# ===========================================================
# 🔍 Multi-Angle Retrieval Prompts
# ===========================================================
RISK_ANGLES = [
    "blockers, dependencies, or blocked tickets that could delay delivery",
    "scope changes or new work added outside of original sprint planning",
    "team capacity, workload, morale, or attrition signals",
    "SEV-1 incidents, postmortems, outages, or unassigned critical remediation tickets",
    "status updates and whether they match the evidence in tickets and discussions",
]

# ===========================================================
# 📣 Human-in-the-Loop / Notification Settings
# ===========================================================
# Lets tests (or any non-interactive run) suppress real Telegram delivery
# without touching the routing/decision-tree logic itself. Defaults to
# enabled so normal runs are unaffected.
TELEGRAM_ALERTS_ENABLED = os.getenv("TELEGRAM_ALERTS_ENABLED", "true").lower() == "true"