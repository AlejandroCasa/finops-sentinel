# Technical Backlog & Architecture Roadmap — FinOps Sentinel

This file tracks prioritized engineering improvements, technical debt, and completed milestones for **FinOps Sentinel**.

## 🎯 Prioritized Backlog (Sprint 2026-W47)

### P1 — Ingestion Expansion, Active Alerting & Resilience
- [ ] **[ingestion]** Batch Ingestion (`POST /api/v1/telemetry/batch`) & LLM Token Cost Calculator (`POST /api/v1/telemetry/llm`): Support bulk cost evaluation and automatic token-to-USD calculation (`model`, `input_tokens`, `output_tokens`) (Impact: 5/5 | Effort: M)
- [ ] **[alerts]** Push Webhook Notifier with Cooldown: Dispatch anomaly notifications to Slack/Teams/Discord webhooks (`FINOPS_WEBHOOK_URL`) with per-service deduplication cooldown (Impact: 4/5 | Effort: S)
- [ ] **[resilience]** Graceful Shutdown & Traffic Simulator: Implement `SIGTERM`/`SIGINT` draining in FastAPI `lifespan` and add `scripts/simulate_traffic.py` (`httpx`) for multi-service billing simulation (Impact: 4/5 | Effort: S)
- [ ] **[detector]** Configurable Statistical Detection (`Z-Score` & `EWMA`): Support standard-deviation (`Z-Score`) and exponentially weighted moving average (`EWMA`) strategies alongside the classic +25% threshold via `pydantic-settings` (Impact: 4/5 | Effort: M)
- [ ] **[focus]** FinOps FOCUS™ 1.0 Ingestion (`POST /api/v1/telemetry/focus`): Support standard FinOps Open Cost and Usage Specification payloads (`BilledCost`, `EffectiveCost`, `ServiceName`, `RegionId`) (Impact: 4/5 | Effort: S)

### P2 — Extreme Verification, Fuzzing & DevSecOps Gates
- [ ] **[devsecops]** Advanced Security & Verification Tooling (`mutmut`, `semgrep`/`codeql`, `atheris`, `trivy`) in CI/CD (`.github/workflows/ci.yml`) (Impact: 5/5 | Effort: M)

---

## ✅ Completed Milestones
- [x] **[multi-tenant/persistence/guard]** Multi-Tenant Attribution, SQLite Persistence & Budget Guard Circuit Breaker: Added multi-project isolation (`project`, `environment`, `owner_team`, `commit_sha`), embedded SQLite storage (`sqlite3`), API key security (`X-API-Key` via `pydantic-settings`), and `GET /api/v1/guard/{project}` circuit breaker endpoint (`[[ADR-0013-finops-sentinel-multi-tenant-sqlite-persistence]]`) — Branch: `feat/multi-tenant-persistence-and-guard` (`2026-11-16`)
- [x] **[ci/shift-left]** Shift-Left Pre-Commit & Commitizen Integration: Added `.pre-commit-config.yaml` with offline deterministic hooks and `commitizen` conventional commit validation (`[[ADR-0009-finops-sentinel-cicd-devsecops-suite]]`) — Branch: `chore/pre-commit-commitizen` (`2026-11-13`)
- [x] **[observability]** Prometheus Metrics Exporter (`/metrics`): Implemented native zero-dependency Prometheus 0.0.4 text exposition exporter tracking `finops_telemetry_ingested_total`, `finops_anomalies_detected_total`, and `finops_service_cost_amount_gauge` with thread-safe registry, k8s pod scrape annotations, and 100% test coverage (`[[ADR-0012-finops-sentinel-prometheus-metrics-exporter]]`) — Branch: `feat/observability-prometheus-metrics` (`2026-11-11`)
- [x] **[cicd/qa]** Full CI/CD & Quality Gate Suite: Integrated `black`, `isort`, `ruff`, `mypy` (strict), `bandit` (SAST), `pip-audit` (SCA), `radon` & `xenon` (complexity rank `A`), and `pytest-cov` (`>=85%`) with automated GitHub Actions pipeline (`.github/workflows/ci.yml`) (`[[ADR-0009-finops-sentinel-cicd-devsecops-suite]]`) — Branch: `feat/cicd-devsecops-pipeline` (`2026-11-08`)
- [x] **[api/k8s]** Dedicated `/healthz` Endpoint & Local Kubernetes (`k3s`) Manifests: Added `GET /healthz` liveness/readiness endpoint and declarative `k8s/deployment.yaml` + `k8s/service.yaml` with hardened `securityContext` (`runAsNonRoot: true`, `UID 10001`, `readOnlyRootFilesystem: true`, capabilities dropped) (`[[ADR-0005-hardened-k8s-manifests-and-healthz]]`) — Branch: `feat/k8s-manifests-and-healthz` (`2026-11-04`)
- [x] **[detector]** Bounded Sliding Window & Baseline Poisoning Protection: Replaced unbounded `list` with `collections.deque(maxlen=30)` and prevented anomalous spikes from inflating historical mean baseline (`[[ADR-0003-bounded-sliding-window-poisoning-protection]]`) — Branch: `feat/detector-bounded-window` (`2026-11-01`)
- [x] **[docker]** Multi-stage Dockerfile optimized for `uv` with cache mounts, non-root `appuser` (`UID 10001`), and native `HEALTHCHECK` — Commit: `72f13f9` (`2026-11-01`)
- [x] **[detector]** Core in-memory anomaly detection engine (`CostRecord`, `AnomalyReport`, calibration rule, +25% threshold) — Commit: `d3f343e` (`2026-11-01`)
- [x] **[core]** Project initialization with `uv` (Python 3.12, `package = false`) — Commit: `474e5fe` (`2026-11-01`)
