# FinOps Sentinel — Agentic Engineering Governance (`AGENTS.md`)

This repository follows an **Agentic Engineering** workflow governed by strict architectural principles, automated quality gates, and zero-trust container hardening.

## 1. Repository Architecture & Scope
- **Service**: Real-time Cloud & LLM Cost Anomaly Detection API (`FastAPI` + `Pydantic v2`).
- **Package Mode**: `uv` in application mode (`[tool.uv] package = false`, Python 3.12+).
- **Source Layout**:
  - `app/schemas.py`: Pydantic v2 data contracts (`CostRecord`, `AnomalyReport`).
  - `app/detector.py`: Bounded in-memory rolling baseline anomaly engine (`AnomalyDetector`, `deque(maxlen=30)` with baseline poisoning protection).
  - `app/main.py`: FastAPI HTTP endpoints (`GET /healthz`, `POST /api/v1/telemetry`, `GET /api/v1/alerts`, `GET /metrics`).
  - `tests/`: Integration and unit test suite using `pytest` and `httpx`.
  - `BACKLOG.md`: Version-controlled engineering roadmap prioritized by `P0` / `P1` / `P2`.

## 2. Mandatory Quality Gates & CI/CD Standard (Zero-Tolerance Checklist)
No code change may be committed or merged unless **100% of the following gates pass with exit code `0`** locally and in `.github/workflows/ci.yml`:

1. **Dependency Sync**:
   ```bash
   uv sync --frozen
   ```
2. **Formatting, Import Sorting & Linting (`black` + `isort` + `ruff`)**:
   ```bash
   uv run black --check . && uv run isort --check-only --profile black . && uv run ruff check .
   ```
3. **Strict Static Type Checking (`mypy --strict`)**:
   ```bash
   uv run mypy app tests
   ```
4. **Code Complexity & Maintainability (`radon` + `xenon`)**:
   ```bash
   uv run radon cc app/ -a -nb && uv run xenon --max-absolute B --max-modules A --max-average A app/
   ```
5. **Security SAST & Dependency Audit (`bandit` + `pip-audit`)**:
   ```bash
   uv run bandit -c pyproject.toml -r app/ && uv run pip-audit
   ```
6. **Automated Test Suite (`0` warnings, `>= 85%` coverage)**:
   ```bash
   uv run pytest -v --cov=app --cov-report=term-missing --cov-fail-under=85
   ```
7. **Hardened Container Build**:
   ```bash
   docker build -t finops-sentinel:latest .
   ```

## 3. Architectural & Security Guardrails
- **Clean Code & Typing**: 100% type annotations on all functions, methods, and data contracts.
- **Strict Warning Policy**: `pytest` runs with `filterwarnings = ["error"]`.
- **Zero Hardcoded Secrets**: All runtime configuration must be injected via environment variables.
- **Container Hardening**: Multi-stage `Dockerfile` using `uv` cache mounts, `python:3.12-slim` runtime, non-root system user (`UID 10001`, `/usr/sbin/nologin`), `.dockerignore` excluding `tests/`, and native Python `HEALTHCHECK`.
- **Git Governance**: Branch-per-objective (`feat/*`, `fix/*`, `docs/*`, `chore/*`) and atomic Google Conventional Commits.
