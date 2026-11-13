# FinOps Sentinel 🛡️💸

A lightweight, cloud-native **Cloud Cost Anomaly Detection** microservice built with **Python 3.12**, **FastAPI**, **Pydantic v2**, and **uv**.

FinOps Sentinel ingests real-time cost telemetry events across cloud providers or internal platform services, establishes per-service rolling baselines, and detects anomalous budget spikes before billing cycles close.

---

## ✨ Key Capabilities

- **Validated Telemetry Ingestion (`POST /api/v1/telemetry`)**:
  - Enforces strict **Pydantic v2** data contracts ([`CostRecord`](app/schemas.py)): positive cost amounts (`cost_amount > 0`), ISO 4217 currency defaults (`EUR`), and automatic UTC timestamps.
- **Per-Service Calibration & Spike Detection ([`AnomalyDetector`](app/detector.py))**:
  - Isolates historical cost series per service (`cloud-storage`, `compute-cluster`, `managed-db`, etc.).
  - **Calibration Window**: Requires at least 3 prior readings per service before activating anomaly detection (`is_anomaly = False`), preventing cold-start alert fatigue.
  - **Deviation Threshold**: Triggers an anomaly (`is_anomaly = True`) whenever a new reading exceeds the historical mean by more than **+25%**.
- **Alert Audit Trail (`GET /api/v1/alerts`)**:
  - Exposes all persisted [`AnomalyReport`](app/schemas.py) events with exact `deviation_percentage`, `current_cost`, and `historical_mean`.
- **Production-Grade Quality & Container Hardening**:
  - Deterministic dependency management via **`uv`** (`uv.lock`).
  - Zero-tolerance QA pipeline: `ruff`, `mypy` strict typing, and `pytest` with `filterwarnings = ["error"]` and `>= 85%` coverage.
  - Multi-stage [`Dockerfile`](Dockerfile) (`ghcr.io/astral-sh/uv:python3.12-bookworm-slim` builder $\rightarrow$ `python:3.12-slim` runtime) running as a non-privileged system user (`appuser`, `UID 10001`) with a native HTTP `HEALTHCHECK`.

---

## 🚀 Quick Start & Local Simulation (No Cloud Account Required)

FinOps Sentinel is provider-agnostic and can be evaluated locally using synthetic FinOps telemetry traffic.

### 1. Run with `uv` or Docker

```bash
# Option A: Run locally with uv
uv run uvicorn app.main:app --reload --port 8000

# Option B: Build and run hardened production container
docker build -t finops-sentinel:latest .
docker run --rm -p 8000:8000 finops-sentinel:latest
```

Interactive OpenAPI documentation is available at `http://localhost:8000/docs`.

### 2. Simulate a Cloud Cost Spike via `curl`

```bash
# Step 1: Calibration period (3 baseline readings of 100.0 EUR -> is_anomaly: false)
for i in 1 2 3; do
  curl -s -X POST http://localhost:8000/api/v1/telemetry \
    -H "Content-Type: application/json" \
    -d '{"service_name": "gpu-training-cluster", "cost_amount": 100.0, "currency": "EUR"}'
  echo ""
done

# Step 2: Normal variation (+5% = 105.0 EUR -> is_anomaly: false, deviation_percentage: 5.0)
curl -s -X POST http://localhost:8000/api/v1/telemetry \
  -H "Content-Type: application/json" \
  -d '{"service_name": "gpu-training-cluster", "cost_amount": 105.0, "currency": "EUR"}'
echo ""

# Step 3: Anomalous cost spike (+50% = 150.0 EUR -> is_anomaly: true, deviation_percentage: 50.0)
curl -s -X POST http://localhost:8000/api/v1/telemetry \
  -H "Content-Type: application/json" \
  -d '{"service_name": "gpu-training-cluster", "cost_amount": 150.0, "currency": "EUR"}'
echo ""

# Step 4: Inspect persisted alerts
curl -s http://localhost:8000/api/v1/alerts | python3 -m json.tool
```

---

## 🧪 Quality Gates

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy app tests
uv run pytest -v --cov=app --cov-report=term-missing --cov-fail-under=85
```

---

## 🗺️ Architecture Roadmap

See [BACKLOG.md](BACKLOG.md) for the prioritized engineering backlog, including bounded sliding windows (`collections.deque`), baseline-poisoning protection, Z-Score/EWMA statistical detection, Kubernetes (`k3s`) manifests, and Prometheus observability.
