import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)
from pydantic import BaseModel, HttpUrl

from src.config import settings
from src.model import model
from src.utils import download_image, setup_logging

logger = logging.getLogger(__name__)

PREDICTIONS_TOTAL = Counter(
    "predictions_total",
    "Total prediction requests",
    ["status"],
)
PREDICTION_DURATION = Histogram(
    "prediction_duration_seconds",
    "Inference latency",
)
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status_code"],
)


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        HTTP_REQUESTS_TOTAL.labels(
            method=request.method,
            path=request.url.path,
            status_code=str(response.status_code),
        ).inc()
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.LOG_LEVEL)
    model.load()
    yield


app = FastAPI(title="ML Model Serving API", lifespan=lifespan)
app.add_middleware(RequestIDMiddleware)


class PredictRequest(BaseModel):
    image_url: HttpUrl


@app.get("/health")
def health():
    if model.is_loaded():
        return JSONResponse({"status": "ok", "model_loaded": True})
    return JSONResponse(
        {"status": "unavailable", "model_loaded": False},
        status_code=503,
    )


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/v1/predict")
def predict(body: PredictRequest, request: Request):
    request_id = request.state.request_id
    try:
        start = time.perf_counter()
        image = download_image(str(body.image_url))
        result = model.predict(image)
        elapsed = time.perf_counter() - start
    except (ValueError, RuntimeError) as exc:
        PREDICTIONS_TOTAL.labels(status="error").inc()
        status = 400 if isinstance(exc, ValueError) else 500
        return JSONResponse(
            {"error": str(exc), "type": type(exc).__name__},
            status_code=status,
        )
    predictions = result["predictions"]
    PREDICTIONS_TOTAL.labels(status="success").inc()
    PREDICTION_DURATION.observe(elapsed)
    logger.info(
        "Prediction request_id=%s class=%s inference_ms=%.2f",
        request_id,
        predictions[0]["class"],
        elapsed * 1000,
    )
    return {
        "class": predictions[0]["class"],
        "probability": predictions[0]["probability"],
        "top5": predictions,
        "inference_ms": round(elapsed * 1000, 2),
        "request_id": request_id,
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        {"error": str(exc), "type": type(exc).__name__},
        status_code=500,
    )
