import os
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    'host': os.getenv("DB_HOST", "localhost"),
    'database': os.getenv("DB_NAME", "crm_ai"),
    'user': os.getenv("DB_USER", "postgres"),
    'password': os.getenv("DB_PASSWORD"),
    'port': os.getenv("DB_PORT", "5432")
}

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

