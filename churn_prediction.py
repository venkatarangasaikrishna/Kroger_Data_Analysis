# churn.py

import pyodbc
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
from config import CONN_STR

# where to write images
IMG_DIR = Path(__file__).parent / "static/images"
IMG_DIR.mkdir(exist_ok=True, parents=True)

def analysis_churn(threshold_days: int = 90):
    """
    Simple churn visualization:
      - pulls an RFM sample
      - labels churn (Recency > threshold_days)
      - draws a bar chart of active vs. churned counts
    Returns (report_dict, roc_auc_float, image_path_or_None)
    """
    # 1) pull data
    with pyodbc.connect(CONN_STR, timeout=30) as conn:
        rfm = pd.read_sql_query("""
            SELECT TOP 2000
              HSHD_NUM,
              DATEDIFF(day, MAX(PURCHASE_DATE), GETDATE()) AS Recency
            FROM [400_transactions]
            WHERE PURCHASE_DATE IS NOT NULL
            GROUP BY HSHD_NUM
            ORDER BY MAX(PURCHASE_DATE) DESC
        """, conn)

    if rfm.empty:
        # no data
        return {}, 0.0, None

    # 2) label churn
    rfm["Churn"] = (rfm["Recency"] > threshold_days).astype(int)

    # 3) count
    counts = rfm["Churn"].value_counts().sort_index()
    # ensure both bars present
    counts = counts.reindex([0, 1], fill_value=0)
    labels = ["Active", "Churned"]

    # 4) plot bar chart
    fig, ax = plt.subplots(figsize=(4, 4))
    ax.bar(labels, counts.values)
    ax.set_title("Customer Churn Distribution")
    ax.set_ylabel("Number of Customers")
    plt.tight_layout()

    # 5) save image
    img_name = "churn_dist.png"
    fig.savefig(IMG_DIR / img_name, dpi=100)
    plt.close(fig)

    # 6) return empty report + zero AUC (so your template skips table & ROC but shows image)
    return {}, 0.0, f"images/{img_name}"
