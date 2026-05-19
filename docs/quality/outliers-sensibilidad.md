# Análisis de sensibilidad — clasificación de outliers CP-01a

Verifica que la conclusión *snap-to-node domina* del ADR-0011 §Diagnóstico no depende de la elección puntual de los dos umbrales heurísticos más sensibles del clasificador (`UMBRAL_RATIO_SNAP_ENDPOINTS`, `UMBRAL_PCT_VIA_FILTRADA`). Se re-clasifica el **mismo set de outliers** sobre una grilla 3×3 y se observa cómo varía la atribución.

Grilla: `ratio_snap ∈ {0.50, 0.55, 0.60}` × `pct_vía_filtrada ∈ {0.15, 0.20, 0.25}`. Total outliers re-clasificados: **22 / 100**.

Regenerar con `uv run --project core-python python tools/analyze_outliers.py`.

## Conteos por causa (combinación de umbrales)

| ratio | %vía | `snap_endpoints` | `snap_corto` | `turn_penalty` | `via_filtrada` | `simplify` | `residual` |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.50 | 0.15 | 12 | 3 | 0 | 3 | 0 | 4 |
| 0.50 | 0.20 | 12 | 3 | 0 | 3 | 0 | 4 |
| 0.50 | 0.25 | 12 | 3 | 0 | 2 | 0 | 5 |
| 0.55 | 0.15 | 12 | 3 | 0 | 3 | 0 | 4 |
| 0.55 | 0.20 | 12 | 3 | 0 | 3 | 0 | 4 |
| 0.55 | 0.25 | 12 | 3 | 0 | 2 | 0 | 5 |
| 0.60 | 0.15 | 14 | 3 | 0 | 1 | 0 | 4 |
| 0.60 | 0.20 | 14 | 3 | 0 | 1 | 0 | 4 |
| 0.60 | 0.25 | 14 | 3 | 0 | 0 | 0 | 5 |

## % atribuido a snap-to-node (snap_endpoints + snap_corto)

| ratio \ %vía | 0.15 | 0.20 | 0.25 |
|---:|---:|---:|---:|
| 0.50 | 68% | 68% | 68% |
| 0.55 | 68% | 68% | 68% |
| 0.60 | 77% | 77% | 77% |

## Conclusión

En las 9 combinaciones de la grilla, el % de outliers atribuidos a **snap-to-node** se mantiene en el rango **[68%, 77%]** (mediana 68%). La afirmación del ADR-0011 §Diagnóstico (*snap-to-node domina*) es robusta a la elección específica de los dos umbrales más sensibles del clasificador, y no un artefacto del valor particular `ratio_snap=0.55` / `pct_via=0.2` usado por defecto.
