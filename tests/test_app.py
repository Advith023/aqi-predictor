# AQI Predictor by Advith Ashok (github.com/Advith023/aqi-predictor). Copyright (c) 2026 Advith Ashok. All rights reserved. Not licensed for reuse; see LICENSE.
import pytest

from aqi.categories import aqi_category
from app import app


@pytest.mark.parametrize("value,expected", [
    (0, "Good"), (50, "Good"), (50.4, "Satisfactory"), (51, "Satisfactory"),
    (100, "Satisfactory"), (101, "Moderate"), (200, "Moderate"), (201, "Poor"),
    (300, "Poor"), (301, "Very Poor"), (400, "Very Poor"), (401, "Severe"), (1500, "Severe"),
])
def test_category_boundaries(value, expected):
    assert aqi_category(value) == expected


@pytest.mark.parametrize("bad", [-1, float("nan"), None])
def test_category_rejects_invalid(bad):
    with pytest.raises(ValueError):
        aqi_category(bad)


@pytest.fixture
def client():
    return app.test_client()


SAMPLE = {"PM2.5": 80, "PM10": 150, "NO": 10, "NO2": 30, "NOx": 35, "NH3": 20,
          "CO": 1.0, "SO2": 12, "O3": 35, "Benzene": 2, "Toluene": 5, "Xylene": 1}


def test_pages(client):
    assert client.get("/").status_code == 200
    assert client.get("/predict").status_code == 200
    assert client.get("/userlog").status_code == 404  # login removed


def test_form_predict(client):
    r = client.post("/predict", data={k: str(v) for k, v in SAMPLE.items()})
    assert r.status_code == 200 and b'class="aqi"' in r.data


def test_api_predict_and_partial_input(client):
    r = client.post("/api/predict", json=SAMPLE)
    assert r.status_code == 200
    body = r.get_json()
    assert body["category"] == aqi_category(body["aqi"])
    assert client.post("/api/predict", json={"PM2.5": 300}).status_code == 200


def test_api_rejects_bad_input(client):
    assert client.post("/api/predict", json={"PM2.5": "abc"}).status_code == 400
    assert client.post("/api/predict", json={"PM2.5": -5}).status_code == 400
    assert client.post("/api/predict", json={}).status_code == 400
