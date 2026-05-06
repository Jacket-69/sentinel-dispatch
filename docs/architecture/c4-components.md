# C4 Nivel 3 — Components

> **Estado:** placeholder. Solo se diagramarán componentes no triviales (Triaje, Ruteo A*, Despacho).

## Container: API (FastAPI)

```mermaid
flowchart TB
    Router[Router HTTP] --> Triaje[Triaje<br/>árbol MPDS]
    Router --> Routing[Routing<br/>A* + heurística]
    Router --> Dispatch[Dispatch<br/>costo + argmin]
    Triaje --> Dispatch
    Routing --> Dispatch
    Dispatch --> Persistence[Persistence<br/>log inmutable]
```

(Detalle por componente pendiente F2.)
