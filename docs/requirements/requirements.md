# Requisitos — Sentinel-Dispatch

> **Estado:** placeholder. La fuente vigente es `Áreas/Universidad/2026-S1/Gestión de Calidad del Software/Proyecto Sentinel-Dispatch/SRS.md` en el vault y los entregables `SRS_Sentinel-Dispatch.tex/.pdf`. La migración completa al `docs/requirements/requirements.md` vivo se hará en F2 vía `/delegate` (bulk repetitivo).

## Resumen ejecutivo

- **12 RFs** (RF-01 a RF-12): triaje, ruteo A*, despacho, re-despacho, log inmutable, simulación, exportación.
- **8 atributos de calidad** con métricas numéricas: precisión ruteo (±5% vs OSRM), confiabilidad (99.9%), rendimiento (≤1s/50u, ≤300ms/10u), trazabilidad, seguridad.
- **10 reglas de negocio** (RN-01 a RN-10).
- **10 casos límite** (CL-01 a CL-10).
- **12 casos de prueba** (CP-01 a CP-12).
- **8 riesgos** (R-01 a R-08).
- **7 criterios de aceptación**.
- **Dataset de aceptación**: 12 incidentes cubriendo Alpha/Bravo/Charlie/Delta/Echo.

## Trazabilidad

| RF | Historia | Test |
|---|---|---|
| RF-02 | HU-triaje-mpds | tests/unit/triaje/test_mpds_subset.py |
| RF-03 | HU-ruteo-astar | tests/unit/routing/test_astar.py |
| RF-04 | HU-costo-multiobjetivo | tests/unit/dispatch/test_costo.py |
| ... | ... | ... |

(Tabla completa pendiente F2.)
