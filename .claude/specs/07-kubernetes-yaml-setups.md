# Spec: Kubernetes YAML Setups

## Overview
This step fills in all six stub Kubernetes manifests that were scaffolded in earlier steps,
plus adds a `namespace.yaml` to create the namespaces those manifests reference. Together
these 7 files form the complete declarative definition of the ML serving system on Kubernetes:
namespaces, the FastAPI application (Deployment, ConfigMap, Service, HPA), and the monitoring
stack (Prometheus and Grafana Deployments + Services). Every file currently has only a metadata
header; this step writes production-quality `spec` sections for all of them, consistent with
the resource limits, probe configuration, and scaling rules defined in `docs/plan.md` and
`docs/ARCHITECTURE.md`.

## Depends on
- **Step 05 — Terraform Setup**: EKS cluster must exist (or a local `minikube`/`kind` cluster
  is acceptable for development validation).
- **Step 03 — FastAPI Application** and **Step 06 (Dockerfile + Compose)**: the container image
  referenced in `deployment.yaml` must be built and available (ECR URI or local image via
  `minikube image load`).
- `monitoring/prometheus.yml` scrape config (already written in Step 06).
- `monitoring/grafana/dashboard.json` + provisioning config (already written in Step 06).

## Routes
No new routes — this step is infrastructure-only.

## Templates
- **Create:** None
- **Modify:** None

## Files to change
All six existing stubs — each needs a complete `spec` section added:

| File | Current state | What gets added |
|------|--------------|-----------------|
| `k8s/configmap.yaml` | metadata only | `data:` block with LOG_LEVEL, MODEL_NAME, PORT, HOST, MAX_IMAGE_SIZE_MB |
| `k8s/deployment.yaml` | metadata only | `spec:` with 2 replicas, container def, resource requests/limits, liveness + readiness probes, envFrom ConfigMap |
| `k8s/service.yaml` | metadata only | `spec:` with type LoadBalancer, port 80 → 8000 |
| `k8s/hpa.yaml` | metadata only | `spec:` with min 1 / max 5 replicas, CPU target 70% |
| `k8s/monitoring/prometheus.yaml` | metadata only | `spec:` Deployment (1 replica, official image, ConfigMap volume mount) + a second `---` document for its Service (port 9090) |
| `k8s/monitoring/grafana.yaml` | metadata only | `spec:` Deployment (1 replica, official image, dashboard + datasource volume mounts) + a second `---` document for its Service (port 3000) |

## Files to create

```
k8s/
└── namespace.yaml     # Namespace: ml-serving + Namespace: monitoring (two --- documents)
```

## New dependencies
No new pip packages. Requires `kubectl` and a running Kubernetes cluster.

---

## Definition of done

- [ ] `kubectl apply -f k8s/namespace.yaml` creates `ml-serving` and `monitoring` namespaces
      without error
- [ ] `kubectl apply -f k8s/` applies all 4 app manifests cleanly (no validation errors)
- [ ] `kubectl apply -f k8s/monitoring/` applies both monitoring manifests cleanly
- [ ] `kubectl rollout status deployment/ml-api -n ml-serving` reports `successfully rolled out`
- [ ] `kubectl get pods -n ml-serving` shows 2 Running pods
- [ ] `kubectl get hpa -n ml-serving` shows `ml-api-hpa` with MINPODS=1 MAXPODS=5
- [ ] `kubectl port-forward svc/ml-api-service 8080:80 -n ml-serving` then
      `curl localhost:8080/health` returns `{"status":"ok","model_loaded":true}`
- [ ] `kubectl get pods -n monitoring` shows prometheus and grafana pods Running
- [ ] Port-forwarding Grafana (`kubectl port-forward svc/grafana 3000:3000 -n monitoring`)
      opens the Grafana UI at `localhost:3000`
- [ ] All YAML passes `kubectl apply --dry-run=client -f k8s/` with zero errors

---

## Key implementation details

### namespace.yaml
Two `---` separated `Namespace` documents: `ml-serving` (app) and `monitoring`.

### configmap.yaml — data block
```yaml
data:
  MODEL_NAME: "resnet18"
  DEVICE: "cpu"
  HOST: "0.0.0.0"
  PORT: "8000"
  LOG_LEVEL: "INFO"
  MAX_IMAGE_SIZE_MB: "10"
```

### deployment.yaml — critical fields
- `replicas: 2`
- Image: `<ECR_URI>:latest` (use a placeholder; swap at deploy time)
- Resources: requests `cpu: 500m, memory: 512Mi`; limits `cpu: 1000m, memory: 1Gi`
- Liveness probe: `httpGet /health` initialDelaySeconds 30, periodSeconds 10
- Readiness probe: `httpGet /health` initialDelaySeconds 10, periodSeconds 5
- `envFrom` referencing `ml-api-config` ConfigMap

### service.yaml
- `type: LoadBalancer`
- Port 80 → targetPort 8000

### hpa.yaml
- `scaleTargetRef`: the `ml-api` Deployment
- `minReplicas: 1`, `maxReplicas: 5`
- CPU `averageUtilization: 70`

### prometheus.yaml
- Deployment: `prom/prometheus:latest`, mounts `prometheus-config` ConfigMap at `/etc/prometheus/`
- ConfigMap: embeds the scrape config targeting `ml-api-service.ml-serving:8000/metrics`
- Service: `ClusterIP`, port 9090

### grafana.yaml
- Deployment: `grafana/grafana:latest`
- Mounts dashboard JSON and datasource provisioning from ConfigMaps
- Service: `ClusterIP`, port 3000
- Datasource provisioning ConfigMap points at `http://prometheus.monitoring:9090`
