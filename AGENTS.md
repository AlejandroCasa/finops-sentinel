# FinOps Sentinel — Repository Engineering Rules

Inherits global CTO governance from `C:/Users/acasa/.gemini/config/AGENTS.md` and `c:/Workspace/AGENTS.md`.

## 1. Repository Architecture & Scope
- **Service**: Real-time Cloud Cost Anomaly Detection API (`FastAPI` + `Pydantic v2`).
- **Package Mode**: `uv` in application mode (`[tool.uv] package = false`, Python 3.12).
- **Source Layout**:
  - `app/schemas.py`: Pydantic v2 data contracts (`CostRecord`, `AnomalyReport`).
  - `app/detector.py`: In-memory rolling baseline anomaly engine (`AnomalyDetector`).
  - `app/main.py`: FastAPI HTTP endpoints (`POST /api/v1/telemetry`, `GET /api/v1/alerts`).
  - `tests/`: Integration and unit test suite using `pytest` and `httpx`.

## 2. Verified Execution Commands (WSL 2 Ubuntu)
Always run toolchain commands from `c:/Workspace/finops-sentinel` via `wsl bash -lc`:
- **Install / Sync Dependencies**: `wsl bash -lc "uv sync --frozen"`
- **Linter & Formatter**: `wsl bash -lc "uv run ruff check . && uv run ruff format --check ."`
- **Static Type Check**: `wsl bash -lc "uv run mypy app tests"`
- **Test Suite & Coverage (`>= 85%`, `0` warnings)**: `wsl bash -lc "uv run pytest -v --cov=app --cov-report=term-missing --cov-fail-under=85"`
- **Container Build**: `wsl bash -lc "docker build -t finops-sentinel:latest ."`

## 3. Obsidian Knowledge Links
- **Project Hub**: `c:/Workspace/docs/Proyectos/FinOps-Sentinel.md` (`[[FinOps-Sentinel]]`)
- **Functional Spec**: `c:/Workspace/docs/Proyectos/FinOps-Sentinel-Spec.md` (`[[FinOps-Sentinel-Spec]]`)
- **Architecture Decisions**: `c:/Workspace/docs/Arquitectura/ADR-0002-docker-multistage-uv.md`
