import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from src.api import app

_MOCK_PREDICTIONS = {
    "predictions": [
        {"class": "tabby cat", "probability": 0.95},
        {"class": "Egyptian cat", "probability": 0.03},
        {"class": "tiger cat", "probability": 0.01},
        {"class": "lynx", "probability": 0.005},
        {"class": "Persian cat", "probability": 0.005},
    ]
}

_MOCK_IMAGE = Image.new("RGB", (224, 224))


@pytest.fixture(scope="module")
def client():
    with patch("src.api.model") as mock_model, patch(
        "src.api.download_image", return_value=_MOCK_IMAGE
    ):
        mock_model.is_loaded.return_value = True
        mock_model.predict.return_value = _MOCK_PREDICTIONS
        mock_model.load.return_value = None
        with TestClient(app) as c:
            yield c


def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["model_loaded"] is True


def test_health_503_when_model_not_loaded():
    with patch("src.api.model") as mock_model:
        mock_model.is_loaded.return_value = False
        mock_model.load.return_value = None
        with TestClient(app) as c:
            resp = c.get("/health")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "unavailable"
    assert body["model_loaded"] is False


def test_metrics_returns_prometheus_text(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "predictions_total" in resp.text


def test_predict_valid_url(client):
    resp = client.post(
        "/v1/predict",
        json={"image_url": "http://example.com/image.jpg"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "class" in body
    assert "probability" in body
    assert "top5" in body
    assert len(body["top5"]) == 5
    assert "inference_ms" in body
    assert "request_id" in body


def test_predict_invalid_url(client):
    resp = client.post("/v1/predict", json={"image_url": "not-a-url"})
    assert resp.status_code == 422


def test_predict_download_error(client):
    with patch(
        "src.api.download_image",
        side_effect=ValueError("not an image"),
    ):
        resp = client.post(
            "/v1/predict",
            json={"image_url": "http://example.com/file.txt"},
        )
    assert resp.status_code == 400
    body = resp.json()
    assert body["type"] == "ValueError"


def test_response_has_request_id_header(client):
    resp = client.get("/health")
    assert "x-request-id" in resp.headers
    uuid.UUID(resp.headers["x-request-id"])
