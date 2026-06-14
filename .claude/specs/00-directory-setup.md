# Spec: Directory Setup

## Overview
This step creates the complete directory scaffold and supporting files for Project-01 (Basic Model
Serving). It establishes the `src/`, `tests/`, `k8s/`, and `monitoring/` layout that every
subsequent task depends on, and seeds stub files so imports resolve from day one. It also pins
dependencies in `requirements.txt` and documents environment setup in `.env.example`. Nothing runs
yet — the goal is a clean, import-safe skeleton that future specs can build on without restructuring.

## Depends on
Nothing. This is step 00 — the foundation.

## Routes
No new routes.

## Templates
- **Create:** None (no web templates; this is a backend/infra project)
- **Modify:** None

## Files to create

```
projects/project-01/
├── src/
│   ├── __init__.py          # empty, marks src as a package
│   ├── config.py            # stub — Settings class, reads from .env
│   ├── model.py             # stub — ModelWrapper skeleton with TODO body
│   ├── utils.py             # stub — download_image, setup_logging stubs
│   └── api.py               # stub — FastAPI app, 3 empty route handlers
├── tests/
│   ├── __init__.py          # empty
│   ├── test_model.py        # stub — placeholder test that asserts True
│   ├── test_api.py          # stub — placeholder test that asserts True
│   └── test_utils.py        # stub — placeholder test that asserts True
├── k8s/
│   ├── deployment.yaml      # empty skeleton with apiVersion + kind only
│   ├── service.yaml         # empty skeleton
│   ├── configmap.yaml       # empty skeleton
│   ├── hpa.yaml             # empty skeleton
│   └── monitoring/
│       ├── prometheus.yaml  # empty skeleton
│       └── grafana.yaml     # empty skeleton
├── monitoring/
│   ├── prometheus.yml       # scrape config stub (targets api:8000/metrics)
│   └── grafana/
│       └── dashboard.json   # minimal valid JSON {}
├── Dockerfile               # FROM python:3.11-slim skeleton, no COPY yet
├── docker-compose.yml       # services: api, prometheus, grafana — images only
├── requirements.txt         # pinned versions from ai-infra conda env
└── .env.example             # all required env vars with placeholder values
```

## Files to change
- `projects/project-01/` — directory does not exist yet; this step creates it entirely.

## New dependencies
No new pip installs — all packages are already installed in the `ai-infra` conda environment.

`requirements.txt` will pin the following (already installed):
```
torch==2.12.0
torchvision==0.27.0
tensorflow-macos==2.16.2
transformers==5.12.0
numpy==1.26.4
pandas==3.0.3
scikit-learn==1.9.0
fastapi==0.136.3
uvicorn==0.49.0
requests==2.34.2
httpx==0.28.1
pyyaml==6.0.3
python-dotenv==1.2.2
pytest==9.0.3
pytest-asyncio==1.4.0
black==26.5.1
flake8==7.3.0
mypy==2.1.0
prometheus-client>=0.20.0
Pillow==12.2.0
pydantic>=2.9.0
```

## Definition of done
- [ ] `projects/project-01/` exists with the full directory tree above
- [ ] `python -c "from src.config import settings"` runs without error (from inside `project-01/`)
- [ ] `python -c "from src.model import ModelWrapper"` runs without error
- [ ] `python -c "from src.api import app"` runs without error
- [ ] `pytest tests/ -v` runs and collects 3 placeholder tests (all pass)
- [ ] `requirements.txt` exists and `pip install -r requirements.txt --dry-run` succeeds
- [ ] `.env.example` exists with all required keys documented
- [ ] `black --check src/ tests/` passes with zero violations
- [ ] `flake8 src/ tests/` passes with zero violations
