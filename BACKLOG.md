# Technical Backlog & Architecture Roadmap — FinOps Sentinel

This file tracks prioritized engineering improvements, technical debt, and completed milestones for **FinOps Sentinel**.

## 🎯 Prioritized Backlog

### P0 — Critical / Core Engine Resilience
- [ ] **[api/k8s]** Dedicated `/healthz` Endpoint & Local Kubernetes (`k3s`) Manifests: Add `GET /healthz` liveness/readiness endpoint and declarative `k8s/deployment.yaml` + `k8s/service.yaml` with `securityContext` (`runAsNonRoot: true`, `runAsUser: 10001`) (Impact: 4/5 | Effort: S)

### P1 — High-Impact Observability & FinOps Standards
- [ ] **[observability]** Prometheus Metrics Exporter (`/metrics`): Expose `finops_telemetry_ingested_total`, `finops_anomalies_detected_total`, and per-service cost gauges for Grafana dashboards (Impact: 4/5 | Effort: S)
- [ ] **[detector]** Configurable Statistical Detection (Z-Score & EWMA): Support standard-deviation (`Z-Score`) and exponentially weighted moving average (`EWMA`) strategies via `pydantic-settings` (Impact: 4/5 | Effort: M)

### P2 — Ecosystem & Developer Experience
- [ ] **[simulation]** Synthetic Multi-Service Traffic Simulator (`scripts/simulate_traffic.py`): CLI utility using `httpx` to simulate realistic multi-service cloud billing streams and FOCUS™ cost events locally (Impact: 3/5 | Effort: S)

---

## ✅ Completed Milestones
- [x] **[detector]** Bounded Sliding Window & Baseline Poisoning Protection: Replaced unbounded `list` with `collections.deque(maxlen=30)` and prevented anomalous spikes from inflating historical mean baseline (`[[ADR-0003-bounded-sliding-window-poisoning-protection]]`) — Branch: `feat/detector-bounded-window` (`2026-11-01`)
- [x] **[docker]** Multi-stage Dockerfile optimized for `uv` with cache mounts, non-root `appuser` (`UID 10001`), and native `HEALTHCHECK` — Commit: `72f13f9` (`2026-11-01`)
- [x] **[detector]** Core in-memory anomaly detection engine (`CostRecord`, `AnomalyReport`, calibration rule, +25% threshold, and strict `pytest` suite) — Commit: `d3f343e` (`2026-11-01`)
- [x] **[core]** Project initialization with `uv` (Python 3.12, `package = false`) and strict `filterwarnings` policy — Commit: `474e5fe` (`2026-11-01`)
