# Spec: API Setup

## Overview
This step turns the `src/api.py` stub into a fully working FastAPI application that serves the
ResNet18 model over HTTP. Three endpoints are implemented: `/health` for Kubernetes liveness/readiness
probes, `/metrics` for Prometheus scraping, and `/v1/predict` for image classification. The app uses
a lifespan context manager to load the model once at startup, a UUID request-ID middleware for
correlated logging, Prometheus counters and histograms for observability, and a global exception
handler that converts unhandled errors into structured JSON responses. `tests/test_api.py` is
also replaced with real tests using FastAPI's `TestClient`.

## Depends on
- **Step 00 — Directory Setup**: provides `src/api.py` stub, `src/config.py` with all settings,
  and `requirements.txt` with `fastapi`, `uvicorn`, `prometheus-client`, and `httpx` already pinned.
- **Step 01 — Utils**: `download_image()` is called on every predict request to fetch and validate
  the image; `setup_logging()` is invoked at app startup.
- **Step 02 — Model Setup**: `model` singleton and `ModelWrapper` from `src/model.py` — the lifespan
  manager calls `model.load()` at startup; `model.is_loaded()` drives the `/health` status code;
  `model.predict()` runs inference on every predict request.

## Routes
- `GET /health` — liveness + readiness probe; returns `{"status": "ok", "model_loaded": true}`
  with 200, or `{"status": "unavailable", "model_loaded": false}` with 503 if the model is not
  loaded — public
- `GET /metrics` — Prometheus text-format scrape endpoint; returns `generate_latest()` output with
  `Content-Type: text/plain; version=0.0.4` — public
- `POST /v1/predict` — image classification; accepts `{"image_url": "https://..."}`, downloads the
  image, runs inference, returns predictions — public

## Templates
- **Create:** None (backend-only step)
- **Modify:** None

## Files to change
- `src/api.py` — replace all three stub handlers with full implementations; add lifespan context
  manager, request-ID middleware, Prometheus metrics, and global exception handler
- `tests/test_api.py` — replace the single placeholder assertion with real unit tests using
  FastAPI `TestClient`

## Files to create
No new files.

## New dependencies
No new pip installs. `fastapi`, `uvicorn`, `prometheus-client`, `httpx`, `pydantic`, and
`python-multipart` are already in `requirements.txt` and the `ai-infra` conda environment.

## Implementation notes

### Lifespan context manager
Use FastAPI's `@asynccontextmanager` lifespan pattern — call `model.load()` in the startup section
and log a message; the shutdown section can be a no-op for now:
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.LOG_LEVEL)
    model.load()
    yield
    # shutdown: nothing to release

app = FastAPI(title="ML Model Serving API", lifespan=lifespan)
```

### Prometheus metrics
Define three metrics at module level (before the app):
```python
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

PREDICTIONS_TOTAL = Counter(
    "predictions_total", "Total prediction requests", ["status"]
)
PREDICTION_DURATION = Histogram(
    "prediction_duration_seconds", "Inference latency"
)
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "path", "status_code"]
)
```
Record `HTTP_REQUESTS_TOTAL` in the request-ID middleware after the response is returned.

### Request-ID middleware
Add a `BaseHTTPMiddleware` subclass that:
1. Generates a UUID for each request: `request_id = str(uuid.uuid4())`
2. Injects it into request state: `request.state.request_id = request_id`
3. Adds it as a response header: `response.headers["X-Request-ID"] = request_id`
4. Records `HTTP_REQUESTS_TOTAL` with method, path, and status code after the call.

### `GET /health`
```python
@app.get("/health")
def health():
    if model.is_loaded():
        return JSONResponse({"status": "ok", "model_loaded": True})
    return JSONResponse({"status": "unavailable", "model_loaded": False}, status_code=503)
```

### `GET /metrics`
```python
from fastapi.responses import Response

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

### `POST /v1/predict`
Request body (Pydantic model):
```python
class PredictRequest(BaseModel):
    image_url: HttpUrl
```

Handler logic:
1. Extract `request_id` from `request.state.request_id` for logging.
2. Call `download_image(str(body.image_url))` — let `ValueError` and
   `requests.exceptions.RequestException` propagate to the global handler.
3. Wrap inference in `time.perf_counter()` to measure latency.
4. Call `model.predict(image)` — let `RuntimeError` propagate.
5. Record `PREDICTIONS_TOTAL.labels(status="success").inc()` and
   `PREDICTION_DURATION.observe(elapsed)`.
6. Log an INFO message with request_id, inference_ms, and top-1 class.
7. Return:
```python
{
    "class": predictions[0]["class"],
    "probability": predictions[0]["probability"],
    "top5": predictions,
    "inference_ms": round(elapsed * 1000, 2),
    "request_id": request_id,
}
```

### Global exception handler
```python
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    PREDICTIONS_TOTAL.labels(status="error").inc()
    status = 400 if isinstance(exc, ValueError) else 500
    return JSONResponse({"error": str(exc), "type": type(exc).__name__}, status_code=status)
```
Specifically, `ValueError` (bad URL, oversized image, wrong content-type) → 400;
everything else → 500.

### Test strategy for `tests/test_api.py`
Use `fastapi.testclient.TestClient`. The model load is slow, so patch it:
```python
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

@pytest.fixture(scope="module")
def client():
    with patch("src.api.model") as mock_model:
        mock_model.is_loaded.return_value = True
        mock_model.predict.return_value = {
            "predictions": [{"class": "cat", "probability": 0.95}] * 5
        }
        with TestClient(app) as c:
            yield c
```

Tests to write (≥ 6):
- `test_health_ok` — GET /health returns 200 + `{"status": "ok", "model_loaded": true}`
- `test_health_503_when_model_not_loaded` — mock `is_loaded()` → False, expect 503
- `test_metrics_returns_prometheus_text` — GET /metrics returns 200, body contains `predictions_total`
- `test_predict_valid_url` — POST /v1/predict with mocked `download_image`, expect 200 + correct schema
- `test_predict_invalid_url` — POST /v1/predict with `{"image_url": "not-a-url"}`, expect 422
- `test_predict_download_error` — mock `download_image` raising `ValueError`, expect 400
- `test_response_has_request_id_header` — verify `X-Request-ID` header present on predict response

## Definition of done
- [ ] `from src.api import app` imports without error
- [ ] `uvicorn src.api:app` starts without error; `curl localhost:8000/health` returns 200 with
      `{"status": "ok", "model_loaded": true}`
- [ ] `curl localhost:8000/health` returns 503 if called before model is loaded (simulate by
      toggling `model._loaded = False`)
- [ ] `curl localhost:8000/metrics` returns 200 with Prometheus text format containing
      `predictions_total` and `prediction_duration_seconds`
- [ ] `POST /v1/predict` with a valid public image URL returns 200 with keys `class`, `probability`,
      `top5` (list of 5), `inference_ms`, `request_id`
- [ ] `POST /v1/predict` with a malformed URL returns 422 (Pydantic validation error)
- [ ] `POST /v1/predict` with an oversized or non-image URL returns 400
- [ ] Every response includes an `X-Request-ID` header with a valid UUID
- [ ] `pytest tests/test_api.py -v` collects ≥ 6 tests and all pass
- [ ] `black --check src/api.py tests/test_api.py` passes with zero violations
- [ ] `flake8 src/api.py tests/test_api.py` passes with zero violations
