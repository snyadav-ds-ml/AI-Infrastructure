from fastapi import FastAPI

from src.config import settings  # noqa: F401

app = FastAPI(title="ML Model Serving API")


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": False}


@app.get("/metrics")
def metrics():
    return {"metrics": "not implemented"}


@app.post("/v1/predict")
def predict():
    return {"result": "not implemented"}
