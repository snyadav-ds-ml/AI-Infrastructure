# Spec: Dockerfile and Compose Setup

## Overview
This step turns the skeleton `Dockerfile` and `docker-compose.yml` stubs (created in step 00)
into a fully working local development stack. The Dockerfile builds a production-grade image for
the FastAPI ML-serving app — non-root user, minimal attack surface, proper layer caching, and a
built-in health check. The Compose file wires up three services (api, prometheus, grafana) with
correct volume mounts, environment variables, dependency ordering, and a shared network so they
can communicate by service name. After this step, a single `docker compose up` brings the entire
observability stack online locally — a prerequisite for writing Kubernetes manifests in step 07.

## Depends on
- **Step 00 — Directory Setup**: `Dockerfile`, `docker-compose.yml`, `monitoring/prometheus.yml`,
  and `monitoring/grafana/dashboard.json` stubs exist and the overall directory layout is in place.
- **Step 03 — API Setup**: `src/api.py` is fully implemented with `/health`, `/metrics`, and
  `/v1/predict` — the Dockerfile will copy and serve this code.
- **Step 02 — Model Setup**: `src/model.py` loads ResNet18 weights; the container must have network
  access at startup to download the model from PyTorch Hub (or a pre-downloaded `.pth` file can be
  bind-mounted via Compose for faster iteration).

## Routes
No new routes. All routes are served by the existing FastAPI app inside the container.

## Templates
- **Create:** None
- **Modify:** None

## Files to change
- `Dockerfile` — replace 4-line stub with a full production-grade build
- `docker-compose.yml` — replace bare skeleton with fully wired service definitions
- `monitoring/prometheus.yml` — replace stub scrape config with valid targets pointing to `api:8000`

## Files to create
- `monitoring/grafana/provisioning/datasources/prometheus.yaml` — auto-provision Prometheus as
  Grafana datasource so the dashboard loads without manual UI steps

## New dependencies
No new pip packages. Docker Engine ≥ 24 and Docker Compose v2 (`docker compose`) must be installed
locally — no changes to `requirements.txt`.

## Implementation notes

### Dockerfile
Single-stage build from `python:3.11-slim`. Multi-stage is not needed here because we ship source
code (not a compiled binary) and model weights are downloaded at runtime.

```dockerfile
FROM python:3.11-slim

# Layer 1: system deps (rarely changes — cache-friendly)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Layer 2: Python deps (changes less often than src/)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Layer 3: application source (changes most often)
COPY src/ ./src/

# Non-root user for security
RUN useradd --no-create-home --shell /bin/false appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Kubernetes liveness/readiness probe can hit this too
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

Key decisions:
- `--no-install-recommends` keeps the image lean (no docs, man pages, etc.)
- Dependencies copied and installed before `src/` so Docker reuses the pip layer on code-only changes
- `--start-period=60s` gives the model time to download (~400 MB ResNet18 weights) before health
  checks start counting failures
- `--no-create-home` on the non-root user avoids a home directory the app doesn't need

### docker-compose.yml
```yaml
version: "3.9"

networks:
  ml-network:
    driver: bridge

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - LOG_LEVEL=INFO
      - MODEL_DEVICE=cpu
    networks:
      - ml-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

  prometheus:
    image: prom/prometheus:v2.51.0
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
    networks:
      - ml-network
    depends_on:
      - api

  grafana:
    image: grafana/grafana:10.4.0
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_USERS_ALLOW_SIGN_UP=false
    volumes:
      - ./monitoring/grafana/provisioning:/etc/grafana/provisioning:ro
      - ./monitoring/grafana/dashboard.json:/var/lib/grafana/dashboards/dashboard.json:ro
    networks:
      - ml-network
    depends_on:
      - prometheus
```

Key decisions:
- Pin image versions (`v2.51.0`, `10.4.0`) — `latest` breaks reproducibility
- Shared `ml-network` bridge lets Prometheus reach `api:8000` by service name (no IP hardcoding)
- `depends_on` sets start order but does NOT wait for healthy; Prometheus retry config handles
  the race between `api` starting and Prometheus's first scrape
- No `restart: always` in dev Compose — crashes stay visible for debugging

### monitoring/prometheus.yml
```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: ml-api
    static_configs:
      - targets:
          - api:8000
    metrics_path: /metrics
```

`api:8000` resolves via Docker's internal DNS using the service name defined in Compose.

### monitoring/grafana/provisioning/datasources/prometheus.yaml
```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
```

This file is auto-loaded by Grafana on startup. Without it, users must manually add the datasource
through the UI every time the container is recreated.

## Definition of done
- [ ] `docker build -t ml-api .` completes without error and image size is under 1.5 GB
- [ ] `docker run --rm -p 8000:8000 ml-api` starts the server; `curl localhost:8000/health` returns
      200 with `{"status": "ok", "model_loaded": true}`
- [ ] `docker compose up` starts all three services without error
- [ ] `curl localhost:8000/health` returns 200 after the model loads (within ~90s on first run)
- [ ] `curl localhost:9090/-/ready` returns 200 (Prometheus is up)
- [ ] Prometheus UI at `http://localhost:9090/targets` shows `ml-api` with state `UP`
- [ ] `curl localhost:9090/api/v1/query?query=predictions_total` returns data after at least one
      predict request
- [ ] Grafana UI at `http://localhost:3000` is reachable; login with `admin/admin` works
- [ ] Grafana shows "Prometheus" as a connected datasource under Configuration → Data sources
- [ ] `docker compose down` stops and removes all containers cleanly
- [ ] No credentials or secrets are hardcoded in `Dockerfile` or `docker-compose.yml`
- [ ] The non-root user (`appuser`) is confirmed via `docker run --rm ml-api whoami` → `appuser`
