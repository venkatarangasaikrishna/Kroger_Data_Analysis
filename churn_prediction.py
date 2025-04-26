import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_curve, auc, classification_report
import matplotlib
matplotlib.use('Agg')  # Non-GUI backend for server
import matplotlib.pyplot as plt
from pathlib import Path
from config import ENGINE

# Save images here
IMG_DIR = Path(__file__).parent / "static" / "images"
IMG_DIR.mkdir(parents=True, exist_ok=True)

def compute_churn_model(threshold_days=90):
    # 1. Load a filtered transactions dataset
    t = pd.read_sql("""
        SELECT TOP 50000 HSHD_NUM, PURCHASE_DATE, SPEND
        FROM [400_transactions]
        WHERE PURCHASE_DATE IS NOT NULL
    """, con=ENGINE)

    if t.empty:
        return {}, 0, None

    # 2. Preprocessing
    t["PURCHASE_DATE"] = pd.to_datetime(t["PURCHASE_DATE"])
    snapshot = t["PURCHASE_DATE"].max() + pd.Timedelta(days=1)

    # 3. Create RFM features
    rfm = (
        t.groupby("HSHD_NUM")
         .agg(
             Recency   = ("PURCHASE_DATE", lambda x: (snapshot - x.max()).days),
             Frequency = ("HSHD_NUM", "count"),
             Monetary  = ("SPEND", "sum")
         )
         .reset_index()
    )
    rfm["Churn"] = (rfm["Recency"] > threshold_days).astype(int)

    # 4. Feature matrix and label
    X = rfm[["Recency", "Frequency", "Monetary"]]
    y = rfm["Churn"]

    # 5. Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # 6. Train/Test split
    X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.3, random_state=42)

    # 7. Random Forest Classifier
    model = RandomForestClassifier(n_estimators=100, max_depth=6, n_jobs=-1, random_state=42)
    model.fit(X_train, y_train)

    # 8. Predictions
    prob = model.predict_proba(X_test)[:,1]
    preds = model.predict(X_test)

    # 9. ROC Curve
    fpr, tpr, _ = roc_curve(y_test, prob)
    roc_auc = auc(fpr, tpr)

    fig, ax = plt.subplots(figsize=(6,6))
    ax.plot(fpr, tpr, color="#D39B25", lw=2, label=f"AUC = {roc_auc:.2f}")
    ax.plot([0,1],[0,1], color="gray", linestyle="--", lw=1)
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title("Churn Model ROC Curve")
    ax.legend(loc="lower right")
    plt.tight_layout()

    img_path = IMG_DIR / "churn_roc.png"
    fig.savefig(img_path, dpi=150)
    plt.close(fig)

    # 10. Classification Report
    report = classification_report(y_test, preds, output_dict=True)

    return report, roc_auc, "images/churn_roc.png"
