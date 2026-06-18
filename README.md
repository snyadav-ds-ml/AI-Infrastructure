# ML Model Serving — AI Infrastructure Project

A production-style ML system that takes an image URL, runs it through a ResNet18 image classifier, and returns what's in the image. Built end-to-end: REST API → Docker → Kubernetes → monitoring.

---

## What this project does

You send it a URL pointing to an image:

```bash
curl -X POST http://localhost:8000/v1/predict \
  -H "Content-Type: application/json" \
  -d '{"image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4d/Cat_November_2010-1a.jpg/1200px-Cat_November-1a.jpg"}'
```

It responds with what the model thinks is in the image:

```json
{
  "class": "tabby cat",
  "probability": 0.92,
  "top5": [
    {"class": "tabby cat", "probability": 0.92},
    {"class": "tiger cat", "probability": 0.05},
    {"class": "Egyptian cat", "probability": 0.02},
    {"class": "lynx", "probability": 0.005},
    {"class": "Persian cat", "probability": 0.005}
  ],
  "inference_ms": 24.3,
  "request_id": "a3f1c2d4-..."
}
```

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| ML model | ResNet18 (pre-trained on ImageNet, via PyTorch) |
| API | FastAPI |
| Containerization | Docker + Docker Compose |
| Orchestration | Kubernetes (EKS on AWS) |
| Infrastructure | Terraform |
| Monitoring | Prometheus + Grafana |

---

## Project structure

```
.
├── src/
│   ├── api.py          # FastAPI app — the three endpoints
│   ├── model.py        # Loads ResNet18 and runs inference
│   ├── utils.py        # Image downloader, JSON logging
│   └── config.py       # All settings (env vars with defaults)
│
├── tests/              # Unit tests (pytest)
│
├── k8s/                # Kubernetes manifests
│   ├── namespace.yaml
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── configmap.yaml
│   ├── hpa.yaml        # Auto-scales pods under load
│   └── monitoring/
│       ├── prometheus.yaml
│       └── grafana.yaml
│
├── monitoring/
│   ├── prometheus.yml              # Scrape config for docker-compose
│   └── grafana/
│       ├── dashboard.json          # Grafana dashboard
│       └── provisioning/
│           ├── datasources/        # Wires Prometheus as data source
│           └── dashboards/         # Tells Grafana where to find dashboards
│
├── terraform/          # AWS infrastructure (VPC, EKS, ECR)
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## Run locally with Docker Compose

**Prerequisites:** Docker Desktop running.

```bash
# 1. Clone the repo
git clone https://github.com/snyadav-ds-ml/AI-Infrastructure.git
cd AI-Infrastructure

# 2. Start everything (API + Prometheus + Grafana)
docker-compose up --build

# 3. Check the API is healthy
curl http://localhost:8000/health
# → {"status": "ok", "model_loaded": true}

# 4. Run a prediction
curl -X POST http://localhost:8000/v1/predict \
  -H "Content-Type: application/json" \
  -d '{"image_url": "https://your-image-url.com/photo.jpg"}'

# 5. Open monitoring
#    Prometheus → http://localhost:9090
#    Grafana    → http://localhost:3000  (login: admin / admin)
```

> **Note:** The first startup takes ~60 seconds — PyTorch downloads the ResNet18 weights (~45 MB) on the first run.

---

## Run the tests

```bash
# Activate your Python environment first, then:
pytest tests/ -v
```

All 19 tests should pass in under 5 seconds (no network calls — everything is mocked).

---

## API endpoints

| Method | Path | What it does |
|--------|------|-------------|
| `GET` | `/health` | Returns `200 ok` if the model is loaded, `503` if not |
| `GET` | `/metrics` | Prometheus metrics scrape endpoint |
| `POST` | `/v1/predict` | Classifies an image from a URL |

---

## Deploy to Kubernetes (AWS EKS)

**Prerequisites:** AWS CLI configured, Terraform ≥ 1.5, kubectl installed.

```bash
# 1. Provision the AWS infrastructure (VPC + EKS cluster + ECR registry)
cd terraform
terraform init
terraform apply

# 2. Point kubectl at the new cluster (command printed by terraform apply)
aws eks update-kubeconfig --region us-east-1 --name ml-serving-cluster

# 3. Build and push the Docker image to ECR
ECR_URL=$(terraform output -raw ecr_repo_url)
docker build -t $ECR_URL:latest .
docker push $ECR_URL:latest

# 4. Deploy the app
kubectl apply -f ../k8s/namespace.yaml
kubectl apply -f ../k8s/
kubectl apply -f ../k8s/monitoring/

# 5. Watch pods come up
kubectl get pods -n ml-serving
kubectl get pods -n monitoring
```

---

## How auto-scaling works

The `hpa.yaml` manifest tells Kubernetes to:
- Keep at least **1 pod** running at all times
- Add more pods (up to **5**) when CPU usage goes above **70%**
- Scale back down automatically when traffic drops

---

## Configuration

All settings can be overridden with environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_NAME` | `resnet18` | Which model to load |
| `DEVICE` | `cpu` | `cpu` or `cuda` or `mps` |
| `PORT` | `8000` | Port the API listens on |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, or `ERROR` |
| `MAX_IMAGE_SIZE_MB` | `5` | Maximum image size the API will download |

Create a `.env` file in the project root to set these locally (never commit it).

---

## Monitoring dashboards

Once everything is running, Grafana at `localhost:3000` shows:

- **Request rate** — how many predictions per second
- **Latency** — p50 / p95 / p99 inference time
- **Error rate** — failed predictions over time
- **Pod CPU / memory** — resource usage per replica
