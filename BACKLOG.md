# Technical Backlog & Architecture Roadmap — FinOps Sentinel

This file tracks prioritized engineering improvements, technical debt, and completed milestones for **FinOps Sentinel**.

## 🎯 Prioritized Backlog (Sprint 2026-W48)

### P1 — Cloud Provider Adapters & Budget Governance
- [ ] **[budgets-api]** Dynamic Per-Project Budget Management API (`PUT /api/v1/guard/{project}/budget`): Allow platform teams to configure custom spending limits and anomaly thresholds per tenant dynamically in SQLite (Impact: 5/5 | Effort: S)
- [ ] **[grafana]** Preconfigured Grafana Dashboard & Prometheus Alertmanager Rules: Add declarative JSON dashboard manifests and Alertmanager YAML rules for `finops_telemetry_ingested_total`, `finops_anomalies_detected_total`, and `finops_service_cost_amount_gauge` (Impact: 4/5 | Effort: S)

### P2 — Cloud Billing Exporter Connectors
- [ ] **[connectors]** Cloud Billing Exporter Connectors: Native pull adapters for AWS Cost & Usage Report (CUR 2.0 / FOCUS) and Azure Cost Management exports (Impact: 5/5 | Effort: M)

---

## ✅ Completed Milestones
- [x] **[focus/detector/resilience/fuzzing]** FinOps FOCUS™ 1.0 Ingestion, Configurable Statistical Detection (`Z-Score` & `EWMA`), Graceful Shutdown, Traffic Simulator & Extreme Verification (`atheris`, `mutmut`, `codeql`, `conftest` OPA/Rego): Added `POST /api/v1/telemetry/focus`, `percentage`/`zscore`/`ewma` strategies via `pydantic-settings`, FastAPI `lifespan` SQLite draining, `scripts/simulate_traffic.py`, coverage-guided fuzzing harness (`fuzz/fuzz_telemetry.py`), mutation hardening suite (`tests/test_mutation_hardening.py` with `100.00%` coverage), OPA policies (`policy/docker.rego`, `policy/k8s.rego`), and `.github/workflows/codeql.yml` (`[[ADR-0019-finops-sentinel-focus-statistical-resilience-and-fuzzing]]`) — Branch: `feat/focus-statistical-resilience-and-fuzzing` (`2026-11-16`)
- [x] **[ingestion/llm/webhooks]** Batch Ingestion, LLM Token Cost Calculator & Push Webhook Alerts: Added `POST /api/v1/telemetry/batch` (bulk evaluation 1-500 records), `POST /api/v1/telemetry/llm` (deterministic token-to-USD pricing for GPT-4o, Claude 3.5, Gemini 2.5), and `WebhookNotifier` with per-service anti-spam cooldown window (`[[ADR-0016-finops-sentinel-batch-llm-ingestion-and-webhooks]]`) — Branch: `feat/batch-llm-ingestion-and-webhooks` (`2026-11-16`)
- [x] **[ci/universal-4-phase]** Universal 4-Phase CI/CD Pipeline Standard: Full expansion of `.github/workflows/ci.yml` across Phase 1 (QA/Typing), Phase 2 (SAST/SCA/Complexity), Phase 3 (Extreme Verification/Semgrep/Trivy), and Phase 4 (Supply Chain/Gitleaks/Syft SBOM/IaC/Schemathesis) — Branch: `feat/batch-llm-ingestion-and-webhooks` (`2026-11-16`)
- [x] **[multi-tenant/persistence/guard]** Multi-Tenant Attribution, SQLite Persistence & Budget Guard Circuit Breaker: Added multi-project isolation (`project`, `environment`, `owner_team`, `commit_sha`), embedded SQLite storage (`sqlite3`), API key security (`X-API-Key` via `pydantic-settings`), and `GET /api/v1/guard/{project}` circuit breaker endpoint (`[[ADR-0013-finops-sentinel-multi-tenant-sqlite-persistence]]`) — Branch: `feat/multi-tenant-persistence-and-guard` (`2026-11-16`)
- [x] **[ci/shift-left]** Shift-Left Pre-Commit & Commitizen Integration: Added `.pre-commit-config.yaml` with offline deterministic hooks and `commitizen` conventional commit validation (`[[ADR-0009-finops-sentinel-cicd-devsecops-suite]]`) — Branch: `chore/pre-commit-commitizen` (`2026-11-13`)
- [x] **[observability]** Prometheus Metrics Exporter (`/metrics`): Implemented native zero-dependency Prometheus 0.0.4 text exposition exporter tracking `finops_telemetry_ingested_total`, `finops_anomalies_detected_total`, and `finops_service_cost_amount_gauge` with thread-safe registry, k8s pod scrape annotations, and 100% test coverage (`[[ADR-0012-finops-sentinel-prometheus-metrics-exporter]]`) — Branch: `feat/observability-prometheus-metrics` (`2026-11-11`)
- [x] **[cicd/qa]** Full CI/CD & Quality Gate Suite: Integrated `black`, `isort`, `ruff`, `mypy` (strict), `bandit` (SAST), `pip-audit` (SCA), `radon` & `xenon` (complexity rank `A`), and `pytest-cov` (`>=85%`) with automated GitHub Actions pipeline (`.github/workflows/ci.yml`) (`[[ADR-0009-finops-sentinel-cicd-devsecops-suite]]`) — Branch: `feat/cicd-devsecops-pipeline` (`2026-11-08`)
- [x] **[api/k8s]** Dedicated `/healthz` Endpoint & Local Kubernetes (`k3s`) Manifests: Added `GET /healthz` liveness/readiness endpoint and declarative `k8s/deployment.yaml` + `k8s/service.yaml` with hardened `securityContext` (`runAsNonRoot: true`, `UID 10001`, `readOnlyRootFilesystem: true`, capabilities dropped) (`[[ADR-0005-hardened-k8s-manifests-and-healthz]]`) — Branch: `feat/k8s-manifests-and-healthz` (`2026-11-04`)
- [x] **[detector]** Bounded Sliding Window & Baseline Poisoning Protection: Replaced unbounded `list` with `collections.deque(maxlen=30)` and prevented anomalous spikes from inflating historical mean baseline (`[[ADR-0003-bounded-sliding-window-poisoning-protection]]`) — Branch: `feat/detector-bounded-window` (`2026-11-01`)
- [x] **[docker]** Multi-stage Dockerfile optimized for `uv` with cache mounts, non-root `appuser` (`UID 10001`), and native `HEALTHCHECK` — Commit: `72f13f9` (`2026-11-01`)
- [x] **[detector]** Core in-memory anomaly detection engine (`CostRecord`, `AnomalyReport`, calibration rule, +25% threshold) — Commit: `d3f343e` (`2026-11-01`)
- [x] **[core]** Project initialization with `uv` (Python 3.12, `package = false`) — Commit: `474e5fe` (`2026-11-01`)
