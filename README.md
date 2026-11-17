# FinOps Sentinel 🛡️💸 (`v1.0.0` — Final Release)

A lightweight, cloud-native **Cloud & LLM Cost Anomaly Detection** microservice built with **Python 3.12**, **FastAPI**, **Pydantic v2**, and **uv**.

> **Project Status**: **Completed / Production Reference (`v1.0.0`)**. All planned FinOps capabilities (Single/Batch/LLM/FOCUS™ 1.0 ingestion, Configurable Statistical Baselines, Budget Guard Circuit Breaker, SQLite persistence, Webhook Anti-Spam, Prometheus `/metrics`, and 4-Phase Extreme DevSecOps Verification) are delivered and frozen.

FinOps Sentinel ingests real-time cost telemetry events across cloud providers, LLM inference pipelines, and **FinOps FOCUS™ 1.0** billing exports, establishes per-project/environment/service rolling baselines with embedded SQLite persistence, and detects anomalous budget spikes using configurable statistical strategies before billing cycles close.

---

## ✨ Key Capabilities

- **Multi-Format Telemetry Ingestion**:
  - **Single & Batch Ingestion (`POST /api/v1/telemetry` & `POST /api/v1/telemetry/batch`)**: Enforces strict **Pydantic v2** data contracts ([`CostRecord`](app/schemas.py)) with multi-tenant attribution (`project`, `environment`, `owner_team`, `commit_sha`), positive cost amounts (`cost_amount > 0`), ISO 4217 currency defaults (`EUR`), and bulk evaluation of up to 500 records per call.
  - **LLM Token Cost Calculator (`POST /api/v1/telemetry/llm`)**: Deterministic token-to-USD pricing engine ([`app/pricing.py`](app/pricing.py)) for `gpt-4o`, `gpt-4o-mini`, `claude-3-5-sonnet`, `claude-3-5-haiku`, `gemini-2.5-pro`, and `gemini-2.5-flash`.
  - **FinOps FOCUS™ 1.0 Ingestion (`POST /api/v1/telemetry/focus`)**: Native support for the FinOps Open Cost and Usage Specification (`BilledCost`, `EffectiveCost`, `ServiceName`, `RegionId`, `BillingCurrency`, `SubAccountId`).
- **Configurable Statistical Anomaly Detection ([`AnomalyDetector`](app/detector.py))**:
  - Isolates historical cost series per `(project, environment, service_name)` in a bounded `collections.deque(maxlen=30)` with embedded SQLite persistence (`sqlite3`) and **baseline poisoning protection**.
  - **Calibration Window**: Requires at least 3 prior readings per key before activating anomaly detection (`is_anomaly = False`), preventing cold-start alert fatigue.
  - **Configurable Strategies (`FINOPS_DETECTION_STRATEGY`)**: Supports classic percentage threshold (`percentage`, default `+25%`), standard deviation (`zscore`), and exponentially weighted moving average (`ewma`) via `pydantic-settings`.
- **Proactive Webhook Push Alerts with Cooldown ([`WebhookNotifier`](app/notifier.py))**:
  - Dispatches JSON alerts to Slack/Teams/Discord (`FINOPS_WEBHOOK_URL`) with a thread-safe per-service anti-spam cooldown window (`FINOPS_WEBHOOK_COOLDOWN_SECONDS`).
- **Budget Guard Circuit Breaker (`GET /api/v1/guard/{project}`)**:
  - Real-time kill-switch allowing CI/CD pipelines and AI agents to verify spending permission (`allowed: bool`) before running expensive workloads.
- **API Key Perimeter Security (`X-API-Key`) & Graceful Shutdown**:
  - Optional runtime authentication configured via `FINOPS_API_KEY` (`pydantic-settings`) and clean SQLite draining on `SIGTERM`/`SIGINT` via FastAPI `lifespan`.
- **Prometheus Observability Exporter (`GET /metrics`)**:
  - Native, zero-dependency Prometheus 0.0.4 text exposition exporter tracking `finops_telemetry_ingested_total`, `finops_anomalies_detected_total`, and `finops_service_cost_amount_gauge`.
- **4-Phase Zero-Tolerance CI/CD & Container Hardening**:
  - Deterministic dependency management via **`uv`** (`uv.lock`).
  - 4-Phase DevSecOps pipeline: `black`, `isort`, `ruff`, `mypy --strict`, `pytest` (`100%` coverage, `0` warnings), `bandit`, `pip-audit`, `radon`/`xenon`, `semgrep`, `codeql`, `atheris` fuzzing (`fuzz/fuzz_telemetry.py`), `mutmut` mutation testing, `trivy`, `gitleaks`, `syft` CycloneDX SBOM, `conftest` OPA/Rego (`policy/`), and `schemathesis`.
  - Multi-stage [`Dockerfile`](Dockerfile) running as a non-privileged system user (`appuser`, `UID 10001`) with a native HTTP `HEALTHCHECK`.

---

## 🚀 Quick Start & Local Simulation (No Cloud Account Required)

```bash
# Option A: Run locally with uv
uv run uvicorn app.main:app --reload --port 8000

# Option B: Run multi-currency, LLM & FOCUS 1.0 traffic simulation
uv run python -m scripts.simulate_traffic --dry-run

# Option C: Build and run hardened production container
docker build -t finops-sentinel:latest .
docker run --rm -p 8000:8000 finops-sentinel:latest
```

Interactive OpenAPI documentation is available at `http://localhost:8000/docs`.

---

## 🧪 Quality Gates

```bash
uv run black --check . && uv run isort --check-only --profile black . && uv run ruff check .
uv run mypy --strict app tests fuzz scripts
uv run pytest -v --cov=app --cov-report=term-missing --cov-fail-under=85
uv run python -m fuzz.fuzz_telemetry --self-test
```

---

## 🗺️ Architecture Roadmap

See [BACKLOG.md](BACKLOG.md) for the prioritized engineering backlog.
