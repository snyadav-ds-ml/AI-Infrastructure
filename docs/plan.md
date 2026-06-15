# Project-01: Basic Model Serving — Implementation Plan

**Goal:** Build a production-ready ML model serving system that accepts image URLs, runs inference
through ResNet18, and returns predictions — fully containerized, Kubernetes-deployable, and
observable via Prometheus + Grafana.

**Stack:** FastAPI · PyTorch (ResNet18) · Docker · Kubernetes · Prometheus · Grafana

---

## Task Breakdown

| # | Task | Depends On | Est. Effort |
|---|------|-----------|-------------|
| T1 | Project scaffold & config | — | 30 min |
| T2 | Model wrapper | T1 | 45 min |
| T3 | FastAPI application | T2 | 1 hr |
| T4 | Unit tests | T2, T3 | 1 hr |
| T5 | Docker & docker-compose | T3 | 45 min |
| T6 | Integration tests | T5 | 45 min |
| T7 | Kubernetes manifests | T5 | 1 hr |
| T8 | Monitoring (Prometheus + Grafana) | T5, T7 | 1 hr |
| T9 | Load test & benchmarking | T6, T8 | 45 min |

---

## Step-by-Step Sequence

---

### T1 — Project Scaffold & Configuration

**Why first:** Every other task imports from `src/` and reads config. Get this right before writing
any business logic.

**Directory layout to create:**

```
projects/project-01/
├── src/
│   ├── __init__.py
│   ├── config.py       # all settings in one place
│   ├── model.py        # model loading + inference
│   ├── utils.py        # image download, logging, helpers
│   └── api.py          # FastAPI app
├── tests/
│   ├── __init__.py
│   ├── test_model.py
│   ├── test_api.py
│   └── test_utils.py
├── k8s/
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── configmap.yaml
│   ├── hpa.yaml
│   └── monitoring/
│       ├── prometheus.yaml
│       └── grafana.yaml
├── monitoring/
│   ├── prometheus.yml  # scrape config
│   └── grafana/
│       └── dashboard.json
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

**Steps:**
1. Create the directory tree  `AI-Infrasturcture` directory
2. Write `src/config.py` — use `pydantic-settings` or `python-dotenv` to read from `.env`.
   Settings needed: `MODEL_NAME`, `DEVICE`, `HOST`, `PORT`, `LOG_LEVEL`, `MAX_IMAGE_SIZE_MB`
3. Write `.env.example` with all keys documented (never commit `.env`)
4. Write `requirements.txt` pinning exact versions from the conda env

**Validation:** `python -c "from src.config import settings; print(settings)"` runs without error.

---

### T2 — Model Wrapper (`src/model.py`)

**Why second:** The API depends on this, tests depend on this. Isolating model logic makes it easy
to swap models later.

**Steps:**
1. Create a `ModelWrapper` class with:
   - `__init__`: load ResNet18 pre-trained weights, move to configured device, set `eval()` mode
   - `preprocess(image: PIL.Image) -> torch.Tensor`: resize to 224×224, normalize with ImageNet
     mean/std, add batch dim
   - `predict(image: PIL.Image) -> dict`: run forward pass, softmax, return top-5 class names +
     probabilities
   - `is_loaded() -> bool`: health-check helper
2. Load ImageNet class labels from `torchvision.models` or a bundled JSON file
3. Log model load time at startup

**Key detail:** Model must load **once at startup** (module-level singleton), not per-request.
Per-request loading would make p99 latency ~10× worse.

**Validation:** `python -c "from src.model import model; print(model.predict(test_image))"` returns
a dict with `class`, `probability`, `top5`.

---

### T3 — FastAPI Application (`src/api.py`)

**Why third:** Depends on model and config being stable. Build all three endpoints before wiring
up tests.

**Endpoints to implement:**

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness + readiness check |
| GET | `/metrics` | Prometheus scrape endpoint |
| POST | `/v1/predict` | Image classification |

**Steps:**
1. Create FastAPI app with lifespan context manager — model loads in `startup`, releases in
   `shutdown`
2. **`/health`**: return `{"status": "ok", "model_loaded": true}` (503 if model not loaded)
3. **`/metrics`**: return `generate_latest()` from `prometheus_client` with correct content-type
4. **`/v1/predict`**:
   - Accept JSON body: `{"image_url": "https://..."}`
   - Validate URL format with Pydantic
   - Download image via `utils.download_image()` (enforce max size, validate content-type)
   - Run `model.predict()`
   - Record latency histogram + request counter in Prometheus
   - Return: `{"class": "cat", "probability": 0.95, "top5": [...], "inference_ms": 23}`
5. Add global exception handler — catch all errors, log them, return structured JSON error
6. Add request ID middleware (UUID per request, injected into logs)

**Validation:** `uvicorn src.api:app --reload` starts, `curl localhost:8000/health` returns 200.

---

### T4 — Unit Tests (`tests/`)

**Why here:** Tests written after the code is shaped but before Docker — fast feedback loop,
no container overhead.

**Steps:**
1. `test_model.py`:
   - Test `preprocess()` output shape is `(1, 3, 224, 224)`
   - Test `predict()` returns dict with required keys
   - Test `predict()` top-5 probabilities sum ≤ 1.0
   - Test `is_loaded()` returns True after init
2. `test_api.py` (use FastAPI `TestClient`):
   - Test `/health` returns 200 with model loaded
   - Test `/v1/predict` with a valid image URL returns 200 + correct schema
   - Test `/v1/predict` with bad URL returns 422
   - Test `/v1/predict` with oversized image returns 400
3. `test_utils.py`:
   - Test `download_image()` rejects non-image content-types
   - Test `download_image()` enforces size limit

**Run:** `pytest tests/ -v` — all tests must pass before moving to T5.

---

### T5 — Docker & docker-compose

**Why here:** Once the app and tests are green locally, containerize it. This is the artifact
everything else (K8s, CI) depends on.

**Steps:**
1. Write `Dockerfile`:
   ```
   FROM python:3.11-slim
   WORKDIR /app
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt
   COPY src/ ./src/
   RUN useradd -m appuser && chown -R appuser /app
   USER appuser
   EXPOSE 8000
   CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]
   ```
   Key: run as non-root, keep image lean (slim base).

2. Write `docker-compose.yml` with three services:
   - `api` — the FastAPI container, port 8000
   - `prometheus` — official image, mounts `monitoring/prometheus.yml`, port 9090
   - `grafana` — official image, mounts dashboard JSON, port 3000

3. Write `monitoring/prometheus.yml` to scrape `api:8000/metrics` every 15s

4. Build and run: `docker-compose up --build`

**Validation:**
- `curl localhost:8000/health` → 200
- `curl localhost:9090` → Prometheus UI accessible
- `curl localhost:3000` → Grafana UI accessible

---

### T6 — Integration Tests

**Why after Docker:** Integration tests run against the actual container, not mocked internals.
This catches environment issues (missing libs, wrong ports, env vars not injected).

**Steps:**
1. Add a `tests/test_integration.py` that spins up the service via `docker-compose` and hits real
   endpoints
2. Test the full predict flow end-to-end with a real image URL
3. Test that `/metrics` contains expected metric names (`predictions_total`,
   `prediction_duration_seconds`)
4. Test that the service returns 503 on `/health` if model fails to load (mock a bad model path)
5. Add a `Makefile` target: `make test-integration` runs docker-compose + pytest + tears down

**Validation:** `make test-integration` exits 0.

---

### T7 — Kubernetes Manifests (`k8s/`)

**Why after Docker:** K8s pulls the image — you need a working image first. Write manifests to
deploy to a local cluster (minikube or kind) before targeting production.

**Files to write:**

1. **`configmap.yaml`** — non-secret config (LOG_LEVEL, MODEL_NAME, PORT)
2. **`deployment.yaml`**:
   - 2 replicas
   - Container image ref
   - Resource requests: `cpu: 500m, memory: 512Mi`; limits: `cpu: 1000m, memory: 1Gi`
   - Liveness probe: GET `/health` every 10s
   - Readiness probe: GET `/health` (pod only gets traffic when model is loaded)
   - `envFrom` pointing to the ConfigMap
3. **`service.yaml`** — `type: LoadBalancer`, port 80 → 8000
4. **`hpa.yaml`** — min 1, max 5 replicas, scale at 70% CPU

**Steps:**
1. Write the four manifests above
2. `kubectl apply -f k8s/` against minikube
3. `kubectl rollout status deployment/ml-api` — wait for ready
4. `kubectl get pods` — confirm 2 pods running
5. `kubectl port-forward svc/ml-api-service 8080:80` — test predict endpoint

**Validation:** predict endpoint responds through the K8s service, not just local uvicorn.

---

### T8 — Monitoring: Prometheus + Grafana on K8s

**Why last in infra:** Monitoring is observability on top of a running system. Get the system
running first, then instrument it.

**Steps:**
1. Write `k8s/monitoring/prometheus.yaml`:
   - Deployment + Service for Prometheus in `monitoring` namespace
   - ConfigMap with scrape config targeting `ml-api-service.ml-serving:8000/metrics`
2. Write `k8s/monitoring/grafana.yaml`:
   - Deployment + Service for Grafana
   - ConfigMap to auto-provision Prometheus as datasource
3. Build a Grafana dashboard (`monitoring/grafana/dashboard.json`) with panels:
   - Request rate (req/sec)
   - Prediction latency (p50, p95, p99)
   - Error rate
   - CPU and memory usage per pod
4. `kubectl apply -f k8s/monitoring/`
5. Port-forward Grafana and verify metrics are flowing

**Validation:** Grafana shows live data after sending a few requests to the predict endpoint.

---

### T9 — Load Test & Benchmarking

**Why last:** You need the full stack (K8s + HPA + monitoring) running to observe real scaling
behavior.

**Steps:**
1. Install `locust`: `pip install locust`
2. Write `tests/locustfile.py`:
   ```python
   from locust import HttpUser, task
   class PredictUser(HttpUser):
       @task
       def predict(self):
           self.client.post("/v1/predict", json={"image_url": "<test_image_url>"})
   ```
3. Run 3 load scenarios and record results in `docs/benchmarks.md`:
   - 10 users → baseline latency (should be 1 pod)
   - 50 users → watch HPA add pods
   - 200 users → confirm 5-pod ceiling, observe p99
4. Fill in the latency/throughput table in `docs/ARCHITECTURE.md` with real measurements
5. Tune HPA thresholds if scaling behaviour is wrong

**Validation:** p95 latency < 100ms at 50 concurrent users.

---

## Definition of Done

- [ ] `pytest tests/` passes (unit + integration)
- [ ] `docker-compose up` → all three services healthy
- [ ] K8s deployment stable with 2 replicas
- [ ] HPA scales up under load, scales down after 5 min idle
- [ ] Grafana dashboard shows request rate, latency, error rate
- [ ] `docs/benchmarks.md` has measured p50/p95/p99 values
- [ ] No secrets committed (`.env` in `.gitignore`)
- [ ] `black` + `flake8` pass with zero violations

---

## Risk Register

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| ResNet18 weights slow to download at container startup | Medium | Pre-bake weights into image or use init container |
| MPS (Apple GPU) not available in Docker on macOS | High | Force `DEVICE=cpu` in container; MPS only for local dev |
| HPA needs metrics-server installed in cluster | Medium | `minikube addons enable metrics-server` |
| Image URL download fails (network, bad URL) | Medium | Timeout + retry with exponential backoff in `utils.py` |
