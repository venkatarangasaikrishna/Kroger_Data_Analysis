import os
from dotenv import load_dotenv

# ── Read .env once here ─────────────────────────────────────
load_dotenv()  

DB_SERVER = os.getenv("DB_SERVER")
DB_NAME   = os.getenv("DB_NAME")
DB_USER   = os.getenv("DB_USER")
DB_PASS   = os.getenv("DB_PASS")

DRIVER    = "{ODBC Driver 17 for SQL Server}"
CONN_STR  = (
    f"DRIVER={DRIVER};"
    f"SERVER={DB_SERVER},1433;"
    f"DATABASE={DB_NAME};"
    f"UID={DB_USER};PWD={DB_PASS};"
    "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
)

# either from .env or random:
SECRET_KEY = os.getenv("SECRET_KEY") or os.urandom(24)
