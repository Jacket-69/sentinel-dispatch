---
adr: 0001
title: Stack tecnológico inicial — Python + FastAPI + SQLite + HTMX
status: accepted
date: 2026-05-06
deciders: Benjamin López
tags: [adr, stack, arquitectura]
---

# ADR 0001 — Stack tecnológico inicial

## Contexto

Sentinel-Dispatch es un proyecto académico semestral (mayo–julio 2026) con equipo de 1–2 personas, sin operación 24/7 real. Necesita:

- Algoritmos sobre grafo OSM real (A* con heurística admisible).
- API HTTP simple para operador de despacho.
- Frontend mínimo (consola web, ~5 vistas).
- Persistencia con log inmutable.
- Tests automatizables.
- Defendible académicamente y libre de overhead enterprise.

El SRS (sec. 2 stack técnico, R-04) sugiere Python + OSMnx + NetworkX + FastAPI, sin cerrar persistencia ni frontend. Hay que cerrar todas las piezas para arrancar Fase 0.

## Decisión

Stack confirmado:

| Capa | Tecnología | Versión |
|---|---|---|
| Lenguaje | **Python** | 3.12 |
| Packaging | **uv** (Astral) | ≥ 0.5 |
| Lint + format | **ruff** | ≥ 0.8 |
| Typecheck | **mypy** (estricto en dominio puro) | ≥ 1.13 |
| Tests | **pytest** + httpx | ≥ 8.3 |
| Pre-commit | **pre-commit** + ruff + mypy + gitleaks | ≥ 4.0 |
| API | **FastAPI** + Uvicorn | ≥ 0.115 |
| Templates | **Jinja2** (servido por FastAPI) | ≥ 3.1 |
| Frontend | **HTMX + Tailwind + Leaflet**, estética CRT/phosphor | — |
| Persistencia | **SQLite** + **SQLAlchemy 2.x** + **Alembic** + **aiosqlite** | — |
| Grafo OSM | **OSMnx** + **NetworkX** | OSMnx ≥ 2.0 |
| Validación | **Pydantic v2** + **pydantic-settings** | ≥ 2.10 |
| Logs | **structlog** (JSON estructurado) | ≥ 24.4 |
| Métricas | **prometheus-client** | ≥ 0.21 |
| CI | **GitHub Actions** | — |

## Alternativas consideradas

### Lenguaje
- **Python**: elegido. OSMnx solo está en Python; comunidad GIS + algoritmos densa; equipo lo conoce.
- Go / Rust: rechazados. OSMnx no existe; reescribir A* + ingesta OSM agrega 4–6 semanas sin valor académico.

### Packaging
- **uv**: elegido. 10–50× más rápido que pip, lockfile determinista, mantenido por Astral.
- Poetry: descartado. Más lento, equipo no lo conoce.
- pip + requirements.txt: descartado. Sin lockfile real.

### Algoritmos sobre grafo
- **NetworkX**: elegido para v1. Suficiente para IV Región (~50–80k nodos). Si RNF "≤1 s para 50 unidades" rompe → migrar a igraph.
- igraph: opt-in si NetworkX queda corto. 5–20× más rápido en A*.
- graph-tool: descartado. Compilación dolorosa, beneficio marginal vs igraph.

### Persistencia
- **SQLite + SQLAlchemy 2.x + Alembic**: elegido. Un archivo, sin servidor, suficiente para 10 unidades + log de despachos. Migración a Postgres es cambiar la URL y ~3 ajustes de tipo si llega el caso. Bonus académico: equipo aprende los tres frameworks juntos.
- PostgreSQL: descartado v1. Overhead operacional sin beneficio (no hay concurrencia real con 1 operador).
- MongoDB / NoSQL: descartado. Los datos tienen relaciones (unidades ↔ despachos ↔ incidentes); SQL es la opción honesta.

### Frontend
- **HTMX + Tailwind + Leaflet** servido por FastAPI/Jinja2: elegido. Sin build step, sin toolchain JS, sin SPA framework. Las ~5 vistas no justifican React/Vue. Estética CRT/phosphor (verde fósforo sobre negro, scanlines, ASCII art en tablas, mapa sin tiles satelitales) — referencia: minijuegos Watch Dogs 2, FNAF arcade, Hacknet. Distintivo en defensa.
- React/Vue + build separado: descartado. Toolchain de 200 MB, gasto de 1–2 semanas que se restan al A*.
- Streamlit/Gradio: descartado. Mapa interactivo cojo, no se ve profesional para defensa.

### API
- **FastAPI**: elegido. Type hints obligados, OpenAPI gratis, async nativo.
- Flask / Django REST: descartados. No tienen las mismas garantías de tipos / OpenAPI sin plugins.

### CI
- **GitHub Actions**: elegido. Repo en GitHub, integración natural, sin coste para repos públicos.

## Consecuencias

### Positivas
- Stack 100% Python excepto frontend (que es HTML+CSS+JS mínimo). Una sola pila mental.
- Tooling moderno (uv, ruff) reduce fricción de setup y CI.
- Estética CRT diferencia el proyecto en defensa sin costo extra de framework.
- SRS LaTeX se puede regenerar desde `docs/requirements/requirements.md` cuando cambie.
- No requiere cuenta paga (excepto deploy demo, que va por ADR aparte).

### Negativas / costo
- NetworkX puro Python puede no cumplir RNF de 1 s con flota grande; tendremos que migrar a igraph si se rompe (ADR futuro).
- HTMX tiene curva si Fernando viene de SPA frameworks; hay que documentar patrones en `coding-standards.md`.
- mypy estricto en dominio puede ralentizar al inicio; se compensa con bugs prevenidos.
- SQLite no soporta concurrencia de escritura; con 1 operador no es problema real.
- Equipo aprende SQLAlchemy + Alembic en paralelo al proyecto; costo de aprendizaje compensado por valor curricular.

### Neutras
- Pydantic v2 vs Pydantic v1 — v2 obligatorio por FastAPI ≥ 0.115.
- Python 3.12 vs 3.13 — pinneamos 3.12 hasta que OSMnx 2.x confirme soporte estable de 3.13.

## Cumplimiento / verificación

- `pyproject.toml` declara todas las versiones; CI corre con la versión pinneada.
- `pre-commit` con ruff + mypy + gitleaks bloquea push con violaciones.
- `make ci` reproduce el pipeline localmente.
- Cualquier dependencia pesada nueva (>20 MB instalada) requiere issue + ADR.

## Referencias

- [SRS Sentinel-Dispatch — sec. 2 Stack técnico](../../requirements/requirements.md)
- [Metodología de Proyectos — _README](../../../../../Documentos/Celaeno/Recursos/Procesos/Metodología%20de%20Proyectos/_README.md) (vault)
- [Metodología aplicada — Sentinel](../../../../../Documentos/Celaeno/Áreas/Universidad/2026-S1/Gestión%20de%20Calidad%20del%20Software/Proyecto%20Sentinel-Dispatch/Metodología%20aplicada.md) (vault)
- OSMnx 2.0 release notes — https://osmnx.readthedocs.io/
- uv documentation — https://docs.astral.sh/uv/
- HTMX essays — https://htmx.org/essays/

## ADRs relacionados

- [ADR-0002 — Monolito modular (próximo)](0002-monolito-modular.md)
- [ADR-0003 — SQLite v1 con plan de migración (próximo)](0003-sqlite-v1.md)
- [ADR-0004 — Frontend retro/CRT con HTMX (próximo)](0004-frontend-retro-htmx.md)
- [ADR-0005 — Estrategia de deploy demo (pendiente decisión)](0005-deploy-demo.md)
