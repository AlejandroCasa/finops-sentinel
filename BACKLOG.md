# Technical Backlog & Architecture Roadmap — FinOps Sentinel

This file tracks prioritized engineering improvements, technical debt, and completed milestones for **FinOps Sentinel**.

## 🎯 Prioritized Backlog (Sprint 2026-W47)

### P0 — Team Cloud Microservice Core & Ponytail Refactoring
- [ ] **[refactor/ponytail]** Full Codebase Refactoring (`ponytail` principles): Minimize code surface area, eliminate unnecessary wrappers/abstractions, and prefer Python stdlib (`sqlite3`, `statistics`, `urllib.request`) + existing dependencies (`fastapi`, `pydantic`, `httpx`) with the smallest complete diff (Impact: 5/5 | Effort: S)
- [ ] **[multi-tenant]** Multi-Project & Attribution Context: Extend `CostRecord` and `AnomalyReport` with `project`, `environment` (`dev`/`staging`/`prod`), `owner_team`, and `commit_sha` / `pipeline_run_id` for isolated per-project baselines (Impact: 5/5 | Effort: S)
- [ ] **[persistence]** Lightweight SQLite Persistence (`FINOPS_DB_PATH`): Persist sliding windows, budgets, and alerts across container restarts using stdlib `sqlite3` (defaulting to `/tmp/finops_sentinel.db` for read-only rootfs compatibility) (Impact: 5/5 | Effort: M)
- [ ] **[security]** API Key Authentication (`X-API-Key`): Protect write/admin endpoints via `FINOPS_API_KEY` configured through `pydantic-settings` (Impact: 5/5 | Effort: S)
- [ ] **[guard]** Budget Circuit Breaker / Kill-Switch (`GET /api/v1/guard/{project}`): Allow CI/CD pipelines and AI agents to query whether execution is allowed (`allowed: bool`) based on active anomalies or hard budget caps (Impact: 5/5 | Effort: S)

### P1 — Ingestion Expansion, Active Alerting & Resilience
- [ ] **[ingestion]** Batch Ingestion (`POST /api/v1/telemetry/batch`) & LLM Token Cost Calculator (`POST /api/v1/telemetry/llm`): Support bulk cost evaluation and automatic token-to-USD calculation (`model`, `input_tokens`, `output_tokens`) (Impact: 5/5 | Effort: M)
- [ ] **[alerts]** Push Webhook Notifier with Cooldown: Dispatch anomaly notifications to Slack/Teams/Discord webhooks (`FINOPS_WEBHOOK_URL`) with per-service deduplication cooldown (Impact: 4/5 | Effort: S)
- [ ] **[resilience]** Graceful Shutdown & Traffic Simulator: Implement `SIGTERM`/`SIGINT` draining in FastAPI `lifespan` and add `scripts/simulate_traffic.py` (`httpx`) for multi-service billing simulation (Impact: 4/5 | Effort: S)
- [ ] **[detector]** Configurable Statistical Detection (`Z-Score` & `EWMA`): Support standard-deviation (`Z-Score`) and exponentially weighted moving average (`EWMA`) strategies alongside the classic +25% threshold via `pydantic-settings` (Impact: 4/5 | Effort: M)
- [ ] **[focus]** FinOps FOCUS™ 1.0 Ingestion (`POST /api/v1/telemetry/focus`): Support standard FinOps Open Cost and Usage Specification payloads (`BilledCost`, `EffectiveCost`, `ServiceName`, `RegionId`) (Impact: 4/5 | Effort: S)

### P2 — Extreme Verification, Fuzzing & DevSecOps Gates
- [ ] **[devsecops]** Advanced Security & Verification Tooling (`mutmut`, `semgrep`/`codeql`, `atheris`, `trivy`):
  - Mutation testing with `mutmut` on core detection and pricing logic.
  - Semantic SAST with `semgrep` (and/or GitHub `CodeQL` workflow).
  - Coverage-guided fuzzing harness with `atheris` (`tests/fuzz_telemetry.py`).
  - Container image and Kubernetes manifest vulnerability scanning with `trivy` in CI/CD (`.github/workflows/ci.yml`). (Impact: 5/5 | Effort: M)

---

## ✅ Completed Milestones
- [x] **[observability]** Prometheus Metrics Exporter (`/metrics`): Implemented native zero-dependency Prometheus 0.0.4 text exposition exporter tracking `finops_telemetry_ingested_total`, `finops_anomalies_detected_total`, and `finops_service_cost_amount_gauge` with thread-safe registry, k8s pod scrape annotations, and 100% test coverage (`[[ADR-0012-finops-sentinel-prometheus-metrics-exporter]]`) — Branch: `feat/observability-prometheus-metrics` (`2026-11-11`)
- [x] **[cicd/qa]** Full CI/CD & Quality Gate Suite: Integrated `black`, `isort`, `ruff`, `mypy` (strict), `bandit` (SAST), `pip-audit` (SCA), `radon` & `xenon` (complexity rank `A`), and `pytest-cov` (`>=85%`) with automated GitHub Actions pipeline (`.github/workflows/ci.yml`) (`[[ADR-0009-finops-sentinel-cicd-devsecops-suite]]`) — Branch: `feat/cicd-devsecops-pipeline` (`2026-11-08`)
- [x] **[api/k8s]** Dedicated `/healthz` Endpoint & Local Kubernetes (`k3s`) Manifests: Added `GET /healthz` liveness/readiness endpoint and declarative `k8s/deployment.yaml` + `k8s/service.yaml` with hardened `securityContext` (`runAsNonRoot: true`, `UID 10001`, `readOnlyRootFilesystem: true`, capabilities dropped) (`[[ADR-0005-hardened-k8s-manifests-and-healthz]]`) — Branch: `feat/k8s-manifests-and-healthz` (`2026-11-04`)
- [x] **[detector]** Bounded Sliding Window & Baseline Poisoning Protection: Replaced unbounded `list` with `collections.deque(maxlen=30)` and prevented anomalous spikes from inflating historical mean baseline (`[[ADR-0003-bounded-sliding-window-poisoning-protection]]`) — Branch: `feat/detector-bounded-window` (`2026-11-01`)
- [x] **[docker]** Multi-stage Dockerfile optimized for `uv` with cache mounts, non-root `appuser` (`UID 10001`), and native `HEALTHCHECK` — Commit: `72f13f9` (`2026-11-01`)
- [x] **[detector]** Core in-memory anomaly detection engine (`CostRecord`, `AnomalyReport`, calibration rule, +25% threshold, and strict `pytest` suite) — Commit: `d3f343e` (`2026-11-01`)
- [x] **[core]** Project initialization with `uv` (Python 3.12, `package = false`) and strict `filterwarnings` policy — Commit: `474e5fe` (`2026-11-01`)
