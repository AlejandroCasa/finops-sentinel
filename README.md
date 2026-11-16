# FinOps Sentinel 🛡️💸

A lightweight, cloud-native **Cloud Cost Anomaly Detection** microservice built with **Python 3.12**, **FastAPI**, **Pydantic v2**, and **uv**.

FinOps Sentinel ingests real-time cost telemetry events across cloud providers or internal platform services, establishes per-project/environment/service rolling baselines, and detects anomalous budget spikes before billing cycles close.

---

## ✨ Key Capabilities

- **Validated Telemetry Ingestion (`POST /api/v1/telemetry`)**:
  - Enforces strict **Pydantic v2** data contracts ([`CostRecord`](app/schemas.py)): multi-tenant attribution (`project`, `environment`, `owner_team`, `commit_sha`), positive cost amounts (`cost_amount > 0`), ISO 4217 currency defaults (`EUR`), and automatic UTC timestamps.
- **Multi-Tenant Calibration & Spike Detection ([`AnomalyDetector`](app/detector.py))**:
  - Isolates historical cost series per `(project, environment, service_name)` with embedded SQLite persistence (`sqlite3`).
  - **Calibration Window**: Requires at least 3 prior readings per key before activating anomaly detection (`is_anomaly = False`), preventing cold-start alert fatigue.
  - **Deviation Threshold**: Triggers an anomaly (`is_anomaly = True`) whenever a new reading exceeds the historical mean by more than **+25%**.
- **Budget Guard Circuit Breaker (`GET /api/v1/guard/{project}`)**:
  - Real-time kill-switch allowing CI/CD pipelines and AI agents to verify spending permission (`allowed: bool`) before running expensive workloads.
- **API Key Perimeter Security (`X-API-Key`)**:
  - Optional runtime authentication configured via `FINOPS_API_KEY` (`pydantic-settings`).
- **Alert Audit Trail (`GET /api/v1/alerts`)**:
  - Exposes all persisted [`AnomalyReport`](app/schemas.py) events with exact `deviation_percentage`, `current_cost`, and `historical_mean`.
- **Prometheus Observability Exporter (`GET /metrics`)**:
  - Native, zero-dependency Prometheus 0.0.4 text exposition exporter tracking `finops_telemetry_ingested_total`, `finops_anomalies_detected_total`, and `finops_service_cost_amount_gauge`.
  - Native Kubernetes discovery annotations configured in [`k8s/deployment.yaml`](k8s/deployment.yaml) (`prometheus.io/scrape: "true"`).
- **Production-Grade Quality & Container Hardening**:
  - Deterministic dependency management via **`uv`** (`uv.lock`).
  - Zero-tolerance QA pipeline: `ruff`, `mypy` strict typing, `bandit`, `xenon`, and `pytest` with `filterwarnings = ["error"]` and `>= 85%` coverage.
  - Multi-stage [`Dockerfile`](Dockerfile) running as a non-privileged system user (`appuser`, `UID 10001`) with a native HTTP `HEALTHCHECK`.

---

## 🚀 Quick Start & Local Simulation (No Cloud Account Required)

```bash
# Option A: Run locally with uv
uv run uvicorn app.main:app --reload --port 8000

# Option B: Build and run hardened production container
docker build -t finops-sentinel:latest .
docker run --rm -p 8000:8000 finops-sentinel:latest
```

Interactive OpenAPI documentation is available at `http://localhost:8000/docs`.

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

See [BACKLOG.md](BACKLOG.md) for the prioritized engineering backlog.
