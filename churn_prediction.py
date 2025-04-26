# churn_analysis.py
import os, time, json
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_curve, auc, classification_report
from pathlib import Path
from config import ENGINE

IMG_DIR       = Path(__file__).parent / "static" / "images"
IMG_DIR.mkdir(exist_ok=True, parents=True)
CACHE_META    = IMG_DIR / "churn_meta.json"
CACHE_TTL_SEC = 3600  # 1h

def _load_cache():
    if CACHE_META.exists():
        m = json.loads(CACHE_META.read_text())
        if time.time() - m["ts"] < CACHE_TTL_SEC and (IMG_DIR / m["img"]).exists():
            return m["report"], m["auc"], m["img"]
    return None

def _write_cache(report, roc_auc, img_name):
    meta = {"ts": time.time(), "report": report, "auc": roc_auc, "img": img_name}
    CACHE_META.write_text(json.dumps(meta))

def compute_churn_model(threshold_days=90):
    # 1) Try cache
    cached = _load_cache()
    if cached:
        return cached

    # 2) Use SQL to pre-aggregate RFM
    rfm = pd.read_sql(
        """
        SELECT
          HSHD_NUM,
          DATEDIFF(day, MAX(PURCHASE_DATE), GETDATE()) AS Recency,
          COUNT(*) AS Frequency,
          SUM(SPEND) AS Monetary
        FROM [400_transactions]
        WHERE PURCHASE_DATE IS NOT NULL
        GROUP BY HSHD_NUM
        """,
        con=ENGINE,
    )
    if rfm.empty:
        return {}, 0, None

    # 3) Label churn
    rfm["Churn"] = (rfm["Recency"] > threshold_days).astype(int)
    X = rfm[["Recency", "Frequency", "Monetary"]]
    y = rfm["Churn"]

    # 4) Scale & split
    Xs = StandardScaler().fit_transform(X)
    X_train, X_test, y_train, y_test = train_test_split(
        Xs, y, test_size=0.3, random_state=42
    )

    # 5) Fit a small RF
    model = RandomForestClassifier(n_estimators=100, max_depth=6, n_jobs=-1, random_state=42)
    model.fit(X_train, y_train)
    prob = model.predict_proba(X_test)[:,1]
    preds = model.predict(X_test)

    # 6) ROC & plot
    fpr, tpr, _ = roc_curve(y_test, prob)
    roc_auc = auc(fpr, tpr)

    fig, ax = plt.subplots(figsize=(6,6))
    ax.plot(fpr, tpr, lw=2, label=f"AUC={roc_auc:.2f}")
    ax.plot([0,1],[0,1], linestyle="--", lw=1, color="gray")
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title("Churn ROC Curve")
    ax.legend(loc="lower right")
    plt.tight_layout()

    img_name = "churn_roc.png"
    fig.savefig(IMG_DIR / img_name, dpi=150)
    plt.close(fig)

    # 7) Classification report
    report = classification_report(y_test, preds, output_dict=True)

    # 8) Cache & return
    _write_cache(report, roc_auc, img_name)
    return report, roc_auc, f"images/{img_name}"
