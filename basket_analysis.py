import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score
from pathlib import Path
from config import ENGINE

IMG_DIR = Path(__file__).parent / "static" / "images"
IMG_DIR.mkdir(parents=True, exist_ok=True)

def basket_linear_regression_analysis():
    # 1. Load a filtered transaction dataset
    df = pd.read_sql("""
        SELECT TOP 50000 BASKET_NUM, PRODUCT_NUM
        FROM [400_transactions]
        WHERE BASKET_NUM IS NOT NULL AND PRODUCT_NUM IS NOT NULL
    """, con=ENGINE)

    if df.empty:
        return "No data available", None

    # 2. Filter top 100 most frequent products only
    top_products = df['PRODUCT_NUM'].value_counts().nlargest(100).index
    df = df[df['PRODUCT_NUM'].isin(top_products)]

    # 3. Create basket-product matrix
    basket = df.groupby(["BASKET_NUM", "PRODUCT_NUM"]).size().unstack(fill_value=0)
    basket = (basket > 0).astype(int)

    # 4. Pick two most frequent products for modeling
    prod_counts = basket.sum().sort_values(ascending=False)
    top_two = prod_counts.head(2).index.tolist()

    if len(top_two) < 2:
        return "Not enough distinct products to train model", None

    X = basket[[top_two[0]]]
    y = basket[top_two[1]]

    # 5. Train/test split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)

    # 6. Linear Regression model
    model = LinearRegression()
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    score = r2_score(y_test, preds)

    # 7. Plotting
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.barh([str(top_two[0])], model.coef_, color="#D39B25")
    ax.set_xlabel("Coefficient")
    ax.set_title(f"Cross-Sell Prediction\nR² = {score:.2f}")
    plt.tight_layout()

    img_path = IMG_DIR / "basket_lr_importance.png"
    fig.savefig(img_path, dpi=150)
    plt.close(fig)

    return score, "images/basket_lr_importance.png"
