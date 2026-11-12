"""Flask app: estimate AQI from 12 pollutant readings."""
import json
import math
from functools import lru_cache
from pathlib import Path

import joblib
import pandas as pd
from flask import Flask, jsonify, render_template, request

from aqi import FEATURES
from aqi.categories import aqi_category

ROOT = Path(__file__).parent
MODEL_PATH = ROOT / "model" / "model.joblib"
METRICS_PATH = ROOT / "model" / "metrics.json"

app = Flask(__name__)


@lru_cache(maxsize=1)
def load_model():
    return joblib.load(MODEL_PATH)


@lru_cache(maxsize=1)
def load_metrics():
    return json.loads(METRICS_PATH.read_text())


def parse_inputs(source):
    """Return ({feature: float}, [errors]). Blank fields become NaN (model handles missing)."""
    values, errors = {}, []
    for f in FEATURES:
        raw = str(source.get(f, "")).strip()
        if raw == "":
            values[f] = float("nan")
            continue
        try:
            v = float(raw)
        except ValueError:
            errors.append(f"{f} must be a number.")
            continue
        if not math.isfinite(v) or v < 0:
            errors.append(f"{f} must be a non-negative number.")
        values[f] = v
    if not errors and all(v != v for v in values.values()):
        errors.append("Enter at least one pollutant reading.")
    return values, errors


def predict(values):
    bundle = load_model()
    row = pd.DataFrame([values], columns=bundle["features"])
    aqi = max(float(bundle["model"].predict(row)[0]), 0.0)
    return round(aqi), aqi_category(round(aqi))


@app.route("/")
def home():
    return render_template("home.html", metrics=load_metrics())


@app.route("/predict", methods=["GET", "POST"])
def predict_page():
    result, errors, form = None, [], {}
    if request.method == "POST":
        form = request.form
        values, errors = parse_inputs(form)
        if not errors:
            aqi, category = predict(values)
            result = {"aqi": aqi, "category": category}
    return render_template("predict.html", features=FEATURES, form=form, result=result, errors=errors)


@app.post("/api/predict")
def api_predict():
    values, errors = parse_inputs(request.get_json(silent=True) or {})
    if errors:
        return jsonify({"errors": errors}), 400
    aqi, category = predict(values)
    return jsonify({"aqi": aqi, "category": category})


if __name__ == "__main__":
    app.run(debug=True)
