"""Train and evaluate the AQI model.

Split is chronological so the test set is genuinely unseen future data:
  train      2015-01-01 .. 2018-12-31   (model selection uses its last 6 months)
  test       2019-01-01 .. 2020-07-01   (touched once, for the published figures)

Usage:  python train.py
Writes: model/model.joblib, model/metrics.json, docs/*.png
"""
import json
from pathlib import Path

import joblib
import matplotlib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, r2_score, root_mean_squared_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from aqi import FEATURES
from aqi.categories import CATEGORIES, aqi_category

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).parent
SEED = 42
TEST_START = "2019-01-01"
VAL_START = "2018-07-01"


def candidates():
    # Imputation sits inside each pipeline, so it is fitted on training rows only.
    return {
        "Median baseline": DummyRegressor(strategy="median"),
        "Ridge regression": make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), Ridge()),
        "Random forest": make_pipeline(
            SimpleImputer(strategy="median"),
            RandomForestRegressor(n_estimators=150, min_samples_leaf=5, max_features=0.5, n_jobs=-1, random_state=SEED),
        ),
        # Handles missing values natively.
        "Gradient boosting": HistGradientBoostingRegressor(max_iter=500, learning_rate=0.05, random_state=SEED),
    }


def evaluate(y_true, y_pred):
    cat_true = [aqi_category(v) for v in y_true]
    cat_pred = [aqi_category(max(v, 0)) for v in y_pred]
    return {
        "r2": round(r2_score(y_true, y_pred), 3),
        "mae": round(mean_absolute_error(y_true, y_pred), 1),
        "rmse": round(root_mean_squared_error(y_true, y_pred), 1),
        "category_accuracy": round(accuracy_score(cat_true, cat_pred), 3),
        "category_macro_f1": round(f1_score(cat_true, cat_pred, average="macro"), 3),
    }


def main():
    df = pd.read_csv(ROOT / "data" / "city_day.csv", parse_dates=["Date"])
    df = df.dropna(subset=["AQI"])  # target must be known
    train = df[df.Date < TEST_START]
    test = df[df.Date >= TEST_START]
    fit, val = train[train.Date < VAL_START], train[train.Date >= VAL_START]

    # 1. Model selection on the validation window.
    val_scores = {}
    for name, model in candidates().items():
        model.fit(fit[FEATURES], fit.AQI)
        val_scores[name] = evaluate(val.AQI, model.predict(val[FEATURES]))
        print(f"[val]  {name:18s} {val_scores[name]}")
    best = min((n for n in val_scores if n != "Median baseline"), key=lambda n: val_scores[n]["mae"])

    # 2. Refit every candidate on the full training period, score once on test.
    test_scores, preds = {}, {}
    for name, model in candidates().items():
        model.fit(train[FEATURES], train.AQI)
        preds[name] = model.predict(test[FEATURES])
        test_scores[name] = evaluate(test.AQI, preds[name])
        print(f"[test] {name:18s} {test_scores[name]}")
        if name == best:
            final = model

    (ROOT / "model").mkdir(exist_ok=True)
    joblib.dump({"model": final, "features": FEATURES, "name": best}, ROOT / "model" / "model.joblib", compress=3)
    metrics = {
        "selected_model": best,
        "split": {
            "train": f"{train.Date.min():%Y-%m-%d} to {train.Date.max():%Y-%m-%d} ({len(train)} rows)",
            "test": f"{test.Date.min():%Y-%m-%d} to {test.Date.max():%Y-%m-%d} ({len(test)} rows)",
            "validation_for_selection": f"{VAL_START} to {train.Date.max():%Y-%m-%d}",
        },
        "test": test_scores,
        "validation": val_scores,
    }
    (ROOT / "model" / "metrics.json").write_text(json.dumps(metrics, indent=2))

    # 3. Figures.
    docs = ROOT / "docs"
    docs.mkdir(exist_ok=True)
    y, p = test.AQI.to_numpy(), preds[best]
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(y, p, s=4, alpha=0.3)
    lim = [0, np.percentile(np.r_[y, p], 99.5)]
    ax.plot(lim, lim, color="black", lw=1)
    ax.set(xlim=lim, ylim=lim, xlabel="Actual AQI", ylabel="Predicted AQI",
           title=f"{best}: test set 2019–2020 (R² {test_scores[best]['r2']})")
    fig.tight_layout()
    fig.savefig(docs / "predicted_vs_actual.png", dpi=120)

    from sklearn.metrics import ConfusionMatrixDisplay
    fig, ax = plt.subplots(figsize=(7, 6))
    ConfusionMatrixDisplay.from_predictions(
        [aqi_category(v) for v in y], [aqi_category(max(v, 0)) for v in p],
        labels=CATEGORIES, normalize="true", values_format=".2f", ax=ax, colorbar=False)
    ax.set_title("AQI category, row-normalised (test set)")
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    fig.tight_layout()
    fig.savefig(docs / "category_confusion.png", dpi=120)
    print(f"\nSelected: {best}")


if __name__ == "__main__":
    main()
