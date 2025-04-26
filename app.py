import os
import re
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, session
# … your existing imports …
from churn_prediction import compute_churn_model
from config import ENGINE, CONN_STR

from flask import Flask, request, render_template, redirect, url_for, session
from flask_session import Session
from dotenv import load_dotenv
import pyodbc
import pandas as pd
from flask import Flask, render_template


# ─── 1) Load config from .env ─────────────────────────────────────────────────
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

DB_SERVER = os.getenv("DB_SERVER")
DB_NAME   = os.getenv("DB_NAME")
DB_USER   = os.getenv("DB_USER")
DB_PASS   = os.getenv("DB_PASS")
SECRET_KEY = os.getenv("SECRET_KEY", os.urandom(24))

DRIVER   = "{ODBC Driver 17 for SQL Server}"
CONN_STR = (
    f"DRIVER={DRIVER};"
    f"SERVER={DB_SERVER},1433;"
    f"DATABASE={DB_NAME};"
    f"UID={DB_USER};PWD={DB_PASS};"
    "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
)

def get_conn():
    return pyodbc.connect(CONN_STR)

# ─── 2) Flask setup ────────────────────────────────────────────────────────────
app = Flask(__name__)
from churn_prediction import compute_churn_model
app.secret_key = SECRET_KEY
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# ─── 3) Routes ─────────────────────────────────────────────────────────────────

@app.route("/", methods=["GET","POST"])
def homepage():
    msg = ""
    if request.method == "POST":
        u = request.form.get("username","").strip()
        p = request.form.get("password","")
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT password FROM users WHERE username = ?", u)
        row = cur.fetchone()
        cur.close(); conn.close()

        if row and row[0] == p:
            session["loggedin"] = True
            session["username"] = u
            return redirect(url_for("profile", username=u))
        msg = "Incorrect username or password"

    return render_template("homepage.html", msg=msg)

@app.route("/register", methods=["GET","POST"])
def register():
    msg = ""
    if request.method == "POST":
        u = request.form.get("username","").strip()
        p = request.form.get("password","")
        e = request.form.get("email","").strip()

        if not (u and p and e):
            msg = "Please fill out all fields"
        elif not re.fullmatch(r"[^@]+@[^@]+\.[^@]+", e):
            msg = "Invalid email address"
        else:
            conn = get_conn(); cur = conn.cursor()
            cur.execute("SELECT 1 FROM users WHERE username = ?", u)
            if cur.fetchone():
                msg = "Username already exists"
            else:
                cur.execute(
                    "INSERT INTO users(username,password,email) VALUES (?,?,?)",
                    (u, p, e)
                )
                conn.commit()
                session["loggedin"] = True
                session["username"] = u
                cur.close(); conn.close()
                return redirect(url_for("profile", username=u))
            cur.close(); conn.close()

    return render_template("register.html", msg=msg)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("homepage"))

@app.route("/profile/<username>")
def profile(username):
    if not session.get("loggedin"):
        return redirect(url_for("homepage"))
    return render_template("profile.html", username=username)

@app.route("/search", methods=["GET", "POST"])
def search():
    msg = ""
    data = []   # always a list, so the template loop is safe

    if request.method == "POST":
        h = request.form.get("search", "").strip()
        if not re.fullmatch(r"\d+", h):
            msg = "Please enter a valid household number"
        else:
            conn = get_conn()
            cur  = conn.cursor()
            cur.execute("""
                SELECT
                  h.HSHD_NUM, t.BASKET_NUM, t.PURCHASE_DATE,
                  p.PRODUCT_NUM, p.DEPARTMENT, p.COMMODITY,
                  t.SPEND, t.UNITS, t.STORE_R, t.WEEK_NUM, t.YEAR,
                  h.L, h.AGE_RANGE, h.MARITAL, h.INCOME_RANGE,
                  h.HOMEOWNER, h.HSHD_COMPOSITION, h.HH_SIZE, h.CHILDREN
                FROM [400_households] AS h
                JOIN [400_transactions] AS t
                  ON h.HSHD_NUM = t.HSHD_NUM
                JOIN [400_products] AS p
                  ON t.PRODUCT_NUM = p.PRODUCT_NUM
                WHERE h.HSHD_NUM = ?
                ORDER BY h.HSHD_NUM, t.BASKET_NUM, t.PURCHASE_DATE, p.PRODUCT_NUM, p.DEPARTMENT, p.COMMODITY
            """, (h,))
            rows = cur.fetchall()
            cur.close()
            conn.close()

            if rows:
                data = rows
            else:
                msg = f"No data found for household {h}"

    return render_template("search.html", data=data, msg=msg)

@app.route("/upload", methods=["GET","POST"])
def upload():
    msg = ""
    if request.method == "POST":
        # grab the three files
        hfile = request.files.get("400_households")
        tfile = request.files.get("400_transactions")
        pfile = request.files.get("400_products")

        if not (hfile and tfile and pfile):
            msg = "Please upload all three CSV files."
            return render_template("upload.html", msg=msg)

        conn = get_conn()
        cur  = conn.cursor()

        # ─── 1) Load households ─────────────────────────────────
        df_h = pd.read_csv(hfile)
        df_h.columns = df_h.columns.str.strip().str.upper()

        # truncate/text‐to‐type conversions
        df_h["L"]                = df_h["L"].astype(str).str[:1]
        df_h["AGE_RANGE"]        = df_h["AGE_RANGE"].astype(str).str[:20]
        df_h["MARITAL"]          = df_h["MARITAL"].astype(str).str[:20]
        df_h["INCOME_RANGE"]     = df_h["INCOME_RANGE"].astype(str).str[:20]
        df_h["HOMEOWNER"]        = df_h["HOMEOWNER"].astype(str).str[:1]
        df_h["HSHD_COMPOSITION"] = df_h["HSHD_COMPOSITION"].astype(str).str[:100]
        df_h["HH_SIZE"]          = pd.to_numeric(df_h["HH_SIZE"], errors="coerce").fillna(0).astype(int)
        df_h["CHILDREN"]         = pd.to_numeric(df_h["CHILDREN"], errors="coerce").fillna(0).astype(int)

        rec_h = df_h[[
            "HSHD_NUM","L","AGE_RANGE","MARITAL",
            "INCOME_RANGE","HOMEOWNER","HSHD_COMPOSITION",
            "HH_SIZE","CHILDREN"
        ]].to_records(index=False).tolist()

        sql_h = """
        INSERT INTO [400_households]
          (HSHD_NUM,L,AGE_RANGE,MARITAL,
           INCOME_RANGE,HOMEOWNER,HSHD_COMPOSITION,
           HH_SIZE,CHILDREN)
        VALUES (?,?,?,?,?,?,?,?,?)
        """
        cur.executemany(sql_h, rec_h)

        # ─── 2) Load products ───────────────────────────────────
        df_p = pd.read_csv(pfile)
        df_p.columns = df_p.columns.str.strip().str.upper()
        if "BRAND_TY" in df_p.columns:
            df_p.rename(columns={"BRAND_TY": "BRAND_TYPE"}, inplace=True)

        df_p["DEPARTMENT"]           = df_p["DEPARTMENT"].astype(str).str[:50]
        df_p["COMMODITY"]            = df_p["COMMODITY"].astype(str).str[:50]
        df_p["BRAND_TYPE"]           = df_p["BRAND_TYPE"].astype(str).str[:20]
        df_p["NATURAL_ORGANIC_FLAG"] = df_p["NATURAL_ORGANIC_FLAG"].astype(str).str[:1]

        rec_p = df_p[[
            "PRODUCT_NUM","DEPARTMENT","COMMODITY",
            "BRAND_TYPE","NATURAL_ORGANIC_FLAG"
        ]].to_records(index=False).tolist()

        sql_p = """
        INSERT INTO [400_products]
          (PRODUCT_NUM,DEPARTMENT,COMMODITY,
           BRAND_TYPE,NATURAL_ORGANIC_FLAG)
        VALUES (?,?,?,?,?)
        """
        cur.executemany(sql_p, rec_p)

        # ─── 3) Load transactions ────────────────────────────────
        df_t = pd.read_csv(tfile)
        df_t.columns = df_t.columns.str.strip().str.upper()
        if "PURCHASE_" in df_t.columns:
            df_t.rename(columns={"PURCHASE_": "PURCHASE_DATE"}, inplace=True)
        df_t["PURCHASE_DATE"] = pd.to_datetime(
            df_t["PURCHASE_DATE"], format="%d-%b-%y", errors="coerce"
        ).dt.date

        # coerce numerics
        df_t["BASKET_NUM"]  = pd.to_numeric(df_t["BASKET_NUM"], errors="coerce").fillna(0).astype(int)
        df_t["HSHD_NUM"]    = pd.to_numeric(df_t["HSHD_NUM"],   errors="coerce").fillna(0).astype(int)
        df_t["PRODUCT_NUM"] = pd.to_numeric(df_t["PRODUCT_NUM"],errors="coerce").fillna(0).astype(int)
        df_t["SPEND"]       = pd.to_numeric(df_t["SPEND"],      errors="coerce").fillna(0)
        df_t["UNITS"]       = pd.to_numeric(df_t["UNITS"],      errors="coerce").fillna(0).astype(int)
        df_t["STORE_R"]     = pd.to_numeric(df_t["STORE_R"],    errors="coerce").fillna(0).astype(int)
        df_t["WEEK_NUM"]    = pd.to_numeric(df_t["WEEK_NUM"],   errors="coerce").fillna(0).astype(int)
        df_t["YEAR"]        = pd.to_numeric(df_t["YEAR"],       errors="coerce").fillna(0).astype(int)

        rec_t = df_t[[
            "BASKET_NUM","HSHD_NUM","PURCHASE_DATE",
            "PRODUCT_NUM","SPEND","UNITS","STORE_R",
            "WEEK_NUM","YEAR"
        ]].to_records(index=False).tolist()

        sql_t = """
        INSERT INTO [400_transactions]
          (BASKET_NUM,HSHD_NUM,PURCHASE_DATE,
           PRODUCT_NUM,SPEND,UNITS,STORE_R,
           WEEK_NUM,YEAR)
        VALUES (?,?,?,?,?,?,?,?,?)
        """
        cur.executemany(sql_t, rec_t)

        conn.commit()
        cur.close()
        conn.close()

        msg = "✅ All three tables updated successfully!"
    return render_template("upload.html", msg=msg)


@app.route("/dashboard")
def dashboard():
    # TODO: implement your dashboard queries & visualizations
    return render_template("dashboard.html")

from basket_analysis import basket_linear_regression_analysis

@app.route("/analysis/basket")
def analysis_basket():
    r2_score, img = basket_linear_regression_analysis()
    return render_template(
        "analysis_basket.html",
        score=r2_score,
        image=img
    )


@app.route("/analysis/churn")
def analysis_churn():
    report, roc_auc, img = compute_churn_model()
    return render_template(
      "analysis_churn.html",
      report=report,
      roc_auc=roc_auc,
      image=img
    )

# ─── 4) Run app ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001, debug=True)
