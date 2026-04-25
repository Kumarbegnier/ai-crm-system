import os
from dotenv import load_dotenv

load_dotenv()

# Database — overridden to /app/data/crm.db in Docker via Dockerfile ENV
DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "..", "crm.db"))

# Agent
AGENT_MODEL   = os.getenv("AGENT_MODEL", "llama3")
AGENT_TIMEOUT = int(os.getenv("AGENT_TIMEOUT_SECONDS", "30"))

# Auth
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")

# CORS — comma-separated list of allowed origins
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
