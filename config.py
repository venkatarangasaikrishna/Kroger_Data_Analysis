import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, URL

# ─── Load environment variables ────────────────────────────────────────────────
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

DB_SERVER = os.getenv("DB_SERVER")
DB_NAME   = os.getenv("DB_NAME")
DB_USER   = os.getenv("DB_USER")
DB_PASS   = os.getenv("DB_PASS")

DRIVER    = "ODBC Driver 17 for SQL Server"

# ─── SQLAlchemy engine for pandas & plotting ─────────────────────────────────
connection_url = URL.create(
    "mssql+pyodbc",
    username=DB_USER,
    password=DB_PASS,
    host=DB_SERVER,
    port=1433,
    database=DB_NAME,
    query={"driver": DRIVER}
)
ENGINE = create_engine(connection_url, fast_executemany=True)

# ─── Raw DBAPI connection string for pyodbc ──────────────────────────────────
CONN_STR = (
    f"DRIVER={{{DRIVER}}};"
    f"SERVER={DB_SERVER},1433;"
    f"DATABASE={DB_NAME};"
    f"UID={DB_USER};PWD={DB_PASS};"
    "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
)
