# FinOps Sentinel — Agentic Engineering Governance (`AGENTS.md`)

This repository follows an **Agentic Engineering** workflow governed by strict architectural principles, automated quality gates, and zero-trust container hardening.

## 1. Repository Architecture & Scope
- **Service**: Real-time Cloud & LLM Cost Anomaly Detection API (`FastAPI` + `Pydantic v2`).
- **Package Mode**: `uv` in application mode (`[tool.uv] package = false`, Python 3.12+).
- **Source Layout**:
  - `app/schemas.py`: Pydantic v2 data contracts (`CostRecord`, `AnomalyReport`).
  - `app/detector.py`: Bounded in-memory rolling baseline anomaly engine (`AnomalyDetector`, `deque(maxlen=30)` with baseline poisoning protection).
  - `app/main.py`: FastAPI HTTP endpoints (`GET /health`, `POST /api/v1/telemetry`, `GET /api/v1/alerts`).
  - `tests/`: Integration and unit test suite using `pytest` and `httpx`.
  - `BACKLOG.md`: Version-controlled engineering roadmap prioritized by `P0` / `P1` / `P2`.

## 2. Mandatory Quality Gates (Zero-Tolerance Pre-Commit Checklist)
No code change may be committed or merged unless **100% of the following gates pass with exit code `0`**:

1. **Dependency Sync**:
   ```bash
   uv sync --frozen
   ```
2. **Linter & Formatter (`ruff`)**:
   ```bash
   uv run ruff check . && uv run ruff format --check .
   ```
3. **Strict Static Type Checking (`mypy --strict`)**:
   ```bash
   uv run mypy app tests
   ```
4. **Automated Test Suite (`0` warnings, `>= 85%` coverage)**:
   ```bash
   uv run pytest -v --cov=app --cov-report=term-missing --cov-fail-under=85
   ```
5. **Hardened Container Build**:
   ```bash
   docker build -t finops-sentinel:latest .
   ```

## 3. Architectural & Security Guardrails
- **Clean Code & Typing**: 100% type annotations on all functions, methods, and data contracts.
- **Strict Warning Policy**: `pytest` runs with `filterwarnings = ["error"]`.
- **Zero Hardcoded Secrets**: All runtime configuration must be injected via environment variables.
- **Container Hardening**: Multi-stage `Dockerfile` using `uv` cache mounts, `python:3.12-slim` runtime, non-root system user (`UID 10001`, `/usr/sbin/nologin`), `.dockerignore` excluding `tests/`, and native Python `HEALTHCHECK`.
- **Git Governance**: Branch-per-objective (`feat/*`, `fix/*`, `docs/*`, `chore/*`) and atomic Google Conventional Commits.
