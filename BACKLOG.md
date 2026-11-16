# Technical Backlog & Architecture Roadmap — FinOps Sentinel

This file tracks prioritized engineering improvements, technical debt, and completed milestones for **FinOps Sentinel**.

## 🎯 Prioritized Backlog (Sprint 2026-W47)

### P0 — High-Impact Team Cloud Microservice Capabilities
- [ ] **[ingestion]** Batch Ingestion (`POST /api/v1/telemetry/batch`) & LLM Token Cost Calculator (`POST /api/v1/telemetry/llm`): High-throughput bulk evaluation and automated token pricing calculation from model, input_tokens, and output_tokens (Impact: 5/5 | Effort: S)
- [ ] **[alerts/webhooks]** Push Notifications with Cooldown (`FINOPS_WEBHOOK_URL`): Automated anomaly dispatch to Slack/Teams/Discord with deduplication window per project (Impact: 5/5 | Effort: S)

### P1 — Core Engine Resilience & FinOps Standards
- [ ] **[resilience]** Graceful Shutdown & Request Draining: Implement SIGTERM/SIGINT handling in FastAPI `lifespan` context for zero-downtime rolling deploys in Kubernetes (Impact: 4/5 | Effort: S)
- [ ] **[simulation]** Synthetic Multi-Service Traffic Simulator (`scripts/simulate_traffic.py`): CLI utility with `httpx` for multi-currency cloud billing streams (Impact: 4/5 | Effort: S)
- [ ] **[focus]** FinOps FOCUS™ 1.0 Schema Ingestion (`POST /api/v1/telemetry/focus`): Standardized billing ingest (`BilledCost`, `EffectiveCost`, `ServiceName`, `RegionId`) (Impact: 4/5 | Effort: S)
- [ ] **[detector]** Configurable Statistical Strategies (Z-Score & EWMA): Statistical anomaly detection strategies via `pydantic-settings` (Impact: 4/5 | Effort: M)

### P2 — DevSecOps Deep Hardening
- [ ] **[mutation]** Mutation Testing Harness with `mutmut` (Impact: 4/5 | Effort: M)
- [ ] **[fuzzing]** Coverage-Guided Fuzzing Harness with `atheris` (`tests/fuzz_telemetry.py`) (Impact: 4/5 | Effort: S)

---

## ✅ Completed Milestones
- [x] **[multi-tenant/persistence/guard]** Multi-Tenant Attribution, SQLite Persistence & Budget Guard Circuit Breaker: Added multi-project isolation (`project`, `environment`, `owner_team`, `commit_sha`), embedded SQLite storage (`sqlite3`), API key security (`X-API-Key` via `pydantic-settings`), and `GET /api/v1/guard/{project}` circuit breaker endpoint (`[[ADR-0013-finops-sentinel-multi-tenant-sqlite-persistence]]`) — Branch: `feat/multi-tenant-persistence-and-guard` (`2026-11-16`)
- [x] **[ci/shift-left]** Shift-Left Pre-Commit & Commitizen Integration: Added `.pre-commit-config.yaml` with offline deterministic hooks and `commitizen` conventional commit validation (`[[ADR-0009-finops-sentinel-cicd-devsecops-suite]]`) — Branch: `chore/pre-commit-commitizen` (`2026-11-13`)
- [x] **[observability]** Native Prometheus Metrics Exporter: Added `GET /metrics` with `finops_telemetry_ingested_total`, `finops_anomalies_detected_total`, and per-service cost gauges (`[[ADR-0012-finops-sentinel-prometheus-metrics-exporter]]`) — Branch: `feat/observability-prometheus-metrics` (`2026-11-11`)
- [x] **[cicd/qa]** Full CI/CD & Quality Gate Suite: Integrated `black`, `isort`, `ruff`, `mypy` (strict), `bandit` (SAST), `pip-audit` (SCA), and `radon`/`xenon` complexity controls (`[[ADR-0009-finops-sentinel-cicd-devsecops-suite]]`) — Branch: `feat/cicd-devsecops-pipeline` (`2026-11-08`)
- [x] **[api/k8s]** Dedicated `/healthz` Endpoint & Local Kubernetes (`k3s`) Manifests: Added `GET /healthz` and declarative `k8s/deployment.yaml` + `k8s/service.yaml` with hardened `securityContext` (`[[ADR-0005-hardened-k8s-manifests-and-healthz]]`) — Branch: `feat/k8s-manifests-and-healthz` (`2026-11-04`)
- [x] **[detector]** Bounded Sliding Window & Baseline Poisoning Protection: Replaced unbounded `list` with `collections.deque(maxlen=30)` (`[[ADR-0003-bounded-sliding-window-poisoning-protection]]`) — Branch: `feat/detector-bounded-window` (`2026-11-01`)
- [x] **[docker]** Multi-stage Dockerfile optimized for `uv` with cache mounts, non-root `appuser` (`UID 10001`), and native `HEALTHCHECK` — Commit: `72f13f9` (`2026-11-01`)
- [x] **[detector]** Core in-memory anomaly detection engine (`CostRecord`, `AnomalyReport`, calibration rule, +25% threshold) — Commit: `d3f343e` (`2026-11-01`)
- [x] **[core]** Project initialization with `uv` (Python 3.12, `package = false`) — Commit: `474e5fe` (`2026-11-01`)
