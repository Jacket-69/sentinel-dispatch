# Arquitectura — overview

> **Estado:** placeholder. Detalle en C4 Context, Container y Components.

## Resumen

Monolito modular Python servido por FastAPI. Cinco módulos por capacidad de negocio: `triaje`, `routing`, `dispatch`, `persistence`, `api` (+ `web` para frontend). Persistencia SQLite local. Grafo OSM cacheado en disco, cargado en memoria al arranque.

## Estilo arquitectónico

Monolito modular (ver ADR-0002 — pendiente). Justificación: equipo de 1–2 personas, 2 meses, sin necesidad real de despliegue independiente.

## Componentes principales

- **`triaje`** — árbol MPDS-subset; lógica pura sin I/O.
- **`routing`** — A* sobre grafo OSM con heurística Haversine; factor_hora y factor_sirena.
- **`dispatch`** — función de costo multiobjetivo; argmin sobre unidades disponibles; re-despacho.
- **`persistence`** — SQLAlchemy 2.x async + SQLite; log inmutable JSON append-only.
- **`api`** — FastAPI; endpoints triaje/despacho/log; OpenAPI auto-generado.
- **`web`** — HTMX + Jinja + Tailwind + Leaflet; estética CRT/phosphor.

## Decisiones clave

- [ADR-0001 — Stack](decisions/0001-stack.md)
- [ADR-0002 — Monolito modular (pendiente)](decisions/0002-monolito-modular.md)
- [ADR-0003 — SQLite v1 (pendiente)](decisions/0003-sqlite-v1.md)
- [ADR-0004 — Frontend retro/CRT con HTMX (pendiente)](decisions/0004-frontend-retro-htmx.md)
- [ADR-0005 — Deploy demo (pendiente)](decisions/0005-deploy-demo.md)

## Diagramas

- [C4 Context](c4-context.md)
- [C4 Container](c4-container.md)
- [C4 Components](c4-components.md)
- [BPMN proceso principal](process-bpmn.md)
