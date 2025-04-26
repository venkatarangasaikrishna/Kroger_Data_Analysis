# basket_analysis.py
import os, time, json
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score
from pathlib import Path
from config import ENGINE

IMG_DIR       = Path(__file__).parent / "static" / "images"
IMG_DIR.mkdir(exist_ok=True, parents=True)
CACHE_META    = IMG_DIR / "basket_lr_meta.json"
CACHE_TTL_SEC = 3600  # 1h

def _load_cache():
    if CACHE_META.exists():
        m = json.loads(CACHE_META.read_text())
        if time.time() - m["ts"] < CACHE_TTL_SEC and (IMG_DIR / m["img"]).exists():
            return m["score"], m["img"]
    return None

def _write_cache(score, img_path):
    meta = {"ts": time.time(), "score": score, "img": img_path}
    CACHE_META.write_text(json.dumps(meta))

def basket_linear_regression_analysis():
    # 1) Try cache
    cached = _load_cache()
    if cached:
        return cached

    # 2) Grab top-20 products by basket count (in SQL)
    top20 = pd.read_sql(
        """
        SELECT TOP 20 PRODUCT_NUM, COUNT_BIG(DISTINCT BASKET_NUM) AS freq
          FROM [400_transactions]
         GROUP BY PRODUCT_NUM
         ORDER BY freq DESC
        """,
        con=ENGINE,
    )
    prods = top20["PRODUCT_NUM"].tolist()
    if len(prods) < 2:
        return "Not enough products", None

    # 3) Only pull rows for those products
    df = pd.read_sql(
        f"""
        SELECT BASKET_NUM, PRODUCT_NUM
          FROM [400_transactions]
         WHERE PRODUCT_NUM IN ({','.join(str(p) for p in prods)})
        """,
        con=ENGINE,
    )
    # 4) Pivot to basket × product binary matrix
    basket = (
        df.groupby(["BASKET_NUM", "PRODUCT_NUM"])
          .size()
          .unstack(fill_value=0)
          .astype(bool)
          .astype(int)
    )

    # 5) Pick top two columns
    sums   = basket.sum().nlargest(2)
    top_two = sums.index.tolist()
    X = basket[[top_two[0]]]
    y = basket[top_two[1]]

    # 6) Train/test split + fit
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, random_state=42
    )
    model = LinearRegression().fit(X_train, y_train)
    score = r2_score(y_test, model.predict(X_test))

    # 7) Plot coefficient
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.barh([str(top_two[0])], model.coef_)
    ax.set_xlabel("Coefficient")
    ax.set_title(f"Cross-Sell Coeff (R²={score:.2f})")
    plt.tight_layout()

    img_name = "basket_lr_importance.png"
    fig.savefig(IMG_DIR / img_name, dpi=150)
    plt.close(fig)

    # 8) Cache & return
    _write_cache(score, img_name)
    return score, f"images/{img_name}"
