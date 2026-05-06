# C4 Nivel 2 — Container

> **Estado:** placeholder. Diagrama detallado pendiente F2 (entregable Tarea 2026-05-07 — **Diseño Arquitectura Físico**).

## Containers

- **Web App (HTMX + Jinja + Tailwind + Leaflet)** — frontend retro CRT, servido por FastAPI.
- **API (FastAPI + Uvicorn)** — endpoints REST + servidor de templates.
- **BD (SQLite + SQLAlchemy 2.x)** — archivo único `data/sentinel.db`.
- **Grafo OSM (en memoria)** — `data/graphs/coquimbo.graphml` cargado al arranque vía OSMnx.

## Diagrama Mermaid (placeholder)

```mermaid
flowchart TB
    subgraph Browser
        UI[Web App<br/>HTMX + Tailwind + Leaflet]
    end
    subgraph Server
        API[FastAPI + Uvicorn<br/>:8000]
        Graph[Grafo OSM<br/>en memoria]
        DB[(SQLite<br/>data/sentinel.db)]
    end
    UI <-->|HTTP + HTMX swaps| API
    API --> Graph
    API --> DB
```
