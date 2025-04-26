import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine

# ─── Load environment variables ────────────────────────────────────────────────
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

DB_SERVER = os.getenv("DB_SERVER")
DB_NAME   = os.getenv("DB_NAME")
DB_USER   = os.getenv("DB_USER")
DB_PASS   = os.getenv("DB_PASS")

DRIVER    = "ODBC Driver 17 for SQL Server"

# ─── Build the SQLAlchemy connection URL manually ──────────────────────────────
# mssql+pyodbc://<user>:<pass>@<server>:<port>/<db>?driver=<driver>
driver_str = DRIVER.replace(" ", "+")  # spaces → pluses for URL
connection_url = (
    f"mssql+pyodbc://{DB_USER}:{DB_PASS}"
    f"@{DB_SERVER}:1433/{DB_NAME}"
    f"?driver={driver_str}"
)

# ─── SQLAlchemy engine for pandas & plotting ─────────────────────────────────
ENGINE = create_engine(connection_url, fast_executemany=True)

# ─── Raw DBAPI connection string for pyodbc ──────────────────────────────────
CONN_STR = (
    f"DRIVER={{{DRIVER}}};"
    f"SERVER={DB_SERVER},1433;"
    f"DATABASE={DB_NAME};"
    f"UID={DB_USER};PWD={DB_PASS};"
    "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
)
