# Technical Backlog & Architecture Roadmap — FinOps Sentinel

This file tracks prioritized engineering improvements, technical debt, and completed milestones for **FinOps Sentinel**.

## 🎯 Prioritized Backlog (Sprint 2026-W46)

### P0 — Real-Time Observability & Metrics
- [ ] **[observability]** Prometheus Metrics Exporter (`/metrics`): Expose `finops_telemetry_ingested_total`, `finops_anomalies_detected_total`, and per-service cost gauges for Grafana dashboards (Impact: 5/5 | Effort: S)

### P1 — Core Engine Resilience & Multi-Cloud Simulation
- [ ] **[resilience]** Graceful Shutdown & Request Draining: Implement SIGTERM/SIGINT signal handling in FastAPI `lifespan` context for seamless rolling updates in Kubernetes (Impact: 4/5 | Effort: S)
- [ ] **[simulation]** Synthetic Multi-Service Traffic Simulator (`scripts/simulate_traffic.py`): CLI utility using `httpx` to simulate realistic multi-service cloud billing streams and FOCUS™ cost events locally (Impact: 4/5 | Effort: S)

### P2 — Advanced Statistical Detection
- [ ] **[detector]** Configurable Statistical Detection (Z-Score & EWMA): Support standard-deviation (`Z-Score`) and exponentially weighted moving average (`EWMA`) strategies via `pydantic-settings` (Impact: 4/5 | Effort: M)

---

## ✅ Completed Milestones
- [x] **[cicd/qa]** Full CI/CD & Quality Gate Suite: Integrated `black`, `isort`, `ruff`, `mypy` (strict), `bandit` (SAST), `pip-audit` (SCA), `radon` & `xenon` (complexity rank `A`), and `pytest-cov` (`>=85%`) with automated GitHub Actions pipeline (`.github/workflows/ci.yml`) (`[[ADR-0009-finops-sentinel-cicd-devsecops-suite]]`) — Branch: `feat/cicd-devsecops-pipeline` (`2026-11-08`)
- [x] **[api/k8s]** Dedicated `/healthz` Endpoint & Local Kubernetes (`k3s`) Manifests: Added `GET /healthz` liveness/readiness endpoint and declarative `k8s/deployment.yaml` + `k8s/service.yaml` with hardened `securityContext` (`runAsNonRoot: true`, `UID 10001`, `readOnlyRootFilesystem: true`, capabilities dropped) (`[[ADR-0005-hardened-k8s-manifests-and-healthz]]`) — Branch: `feat/k8s-manifests-and-healthz` (`2026-11-04`)
- [x] **[detector]** Bounded Sliding Window & Baseline Poisoning Protection: Replaced unbounded `list` with `collections.deque(maxlen=30)` and prevented anomalous spikes from inflating historical mean baseline (`[[ADR-0003-bounded-sliding-window-poisoning-protection]]`) — Branch: `feat/detector-bounded-window` (`2026-11-01`)
- [x] **[docker]** Multi-stage Dockerfile optimized for `uv` with cache mounts, non-root `appuser` (`UID 10001`), and native `HEALTHCHECK` — Commit: `72f13f9` (`2026-11-01`)
- [x] **[detector]** Core in-memory anomaly detection engine (`CostRecord`, `AnomalyReport`, calibration rule, +25% threshold, and strict `pytest` suite) — Commit: `d3f343e` (`2026-11-01`)
- [x] **[core]** Project initialization with `uv` (Python 3.12, `package = false`) and strict `filterwarnings` policy — Commit: `474e5fe` (`2026-11-01`)
