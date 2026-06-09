# Arquitectura — overview

> **Estado:** vigente. Detalle en el documento C4 (Context, Container, Components, Deployment).

## Resumen

Monolito modular Python servido por FastAPI. Cinco módulos por capacidad de negocio: `triaje`, `routing`, `dispatch`, `persistence`, `api` (+ `web` para frontend). Persistencia mediante log JSONL append-only (ADR-0007, supersede a ADR-0003). Grafo OSM cacheado en disco, cargado en memoria al arranque.

## Estilo arquitectónico

Monolito modular (ver ADR-0002 — accepted). Justificación: equipo de 1–2 personas, 2 meses, sin necesidad real de despliegue independiente.

## Componentes principales

- **`triaje`** — árbol MPDS-subset; lógica pura sin I/O.
- **`routing`** — A* sobre grafo OSM con heurística Haversine; factor_hora y factor_sirena.
- **`dispatch`** — función de costo multiobjetivo; argmin sobre unidades disponibles; re-despacho.
- **`persistence`** — log inmutable JSONL append-only (ADR-0007); inmutabilidad por construcción (sin update/delete).
- **`api`** — FastAPI; endpoints triaje/despacho/log; OpenAPI auto-generado.
- **`web`** — HTMX + Jinja + Leaflet; estética CRT/phosphor.

## Decisiones clave

- [ADR-0001 — Stack](decisions/0001-stack.md)
- [ADR-0002 — Monolito modular (accepted)](decisions/0002-monolito-modular.md)
- [ADR-0003 — SQLite v1 (superseded por ADR-0007 — SQLite descartado)](decisions/0003-sqlite-v1.md)
- [ADR-0004 — Frontend retro/CRT con HTMX (deferred, reactivado por ADR-0022)](decisions/0004-frontend-retro-htmx.md)
- [ADR-0005 — Deploy demo (deferred)](decisions/0005-deploy-demo.md)
- [ADR-0007 — Persistencia JSONL append-only (accepted)](decisions/0007-persistencia-jsonl.md)
- [ADR-0022 — Consola web de operador (accepted)](decisions/0022-rescate-frontend-htmx.md)

## Diagramas

- [C4 — Context / Container / Components / Deployment](c4.md)
- [BPMN proceso principal](process-bpmn.bpmn)
