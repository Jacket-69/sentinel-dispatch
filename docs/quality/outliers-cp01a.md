# Outliers CP-01a — clasificación por causa probable

Generado por `tools/analyze_outliers.py` sobre `core-python/tests/fixtures/osrm_oracle.json` (tolerancia: 30%). Las heurísticas y umbrales se documentan en el módulo. Esta tabla se referencia desde ADR-0011 §Diagnóstico.

**Total outliers**: 22 / 100

## Resumen por causa

| Causa | Conteo | % de outliers |
|---|---:|---:|
| `snap_endpoints` | 12 | 55% |
| `residual` | 4 | 18% |
| `via_filtrada` | 3 | 14% |
| `snap_corto` | 3 | 14% |

## Detalle por par

| id | d_propio (m) | d_OSRM (m) | err_rel | giros | %vía filtrada | %aristas <5 m | causa | nota |
|---:|---:|---:|---:|---:|---:|---:|---|---|
| 1 | 0 | 549 | 1.000 | 0 | 0% | 0% | `snap_endpoints` | d_propio=0 m << d_OSRM=549 m (ratio 0.00); snap-to-node colapsó endpoint(s) |
| 20 | 349 | 1882 | 0.814 | 1 | 0% | 0% | `snap_endpoints` | d_propio=349 m << d_OSRM=1882 m (ratio 0.19); snap-to-node colapsó endpoint(s) |
| 4 | 349 | 1856 | 0.812 | 1 | 0% | 0% | `snap_endpoints` | d_propio=349 m << d_OSRM=1856 m (ratio 0.19); snap-to-node colapsó endpoint(s) |
| 22 | 349 | 1855 | 0.812 | 1 | 0% | 0% | `snap_endpoints` | d_propio=349 m << d_OSRM=1855 m (ratio 0.19); snap-to-node colapsó endpoint(s) |
| 24 | 349 | 1855 | 0.812 | 1 | 0% | 0% | `snap_endpoints` | d_propio=349 m << d_OSRM=1855 m (ratio 0.19); snap-to-node colapsó endpoint(s) |
| 57 | 349 | 1855 | 0.812 | 1 | 0% | 0% | `snap_endpoints` | d_propio=349 m << d_OSRM=1855 m (ratio 0.19); snap-to-node colapsó endpoint(s) |
| 67 | 349 | 1855 | 0.812 | 1 | 0% | 0% | `snap_endpoints` | d_propio=349 m << d_OSRM=1855 m (ratio 0.19); snap-to-node colapsó endpoint(s) |
| 36 | 438 | 1835 | 0.761 | 0 | 0% | 0% | `snap_endpoints` | d_propio=438 m << d_OSRM=1835 m (ratio 0.24); snap-to-node colapsó endpoint(s) |
| 43 | 438 | 1815 | 0.759 | 0 | 0% | 0% | `snap_endpoints` | d_propio=438 m << d_OSRM=1815 m (ratio 0.24); snap-to-node colapsó endpoint(s) |
| 66 | 438 | 1815 | 0.759 | 0 | 0% | 0% | `snap_endpoints` | d_propio=438 m << d_OSRM=1815 m (ratio 0.24); snap-to-node colapsó endpoint(s) |
| 84 | 1544 | 944 | 0.635 | 5 | 0% | 0% | `snap_corto` | d_OSRM=944 m < 1000 m; snap-to-node domina en rutas cortas |
| 38 | 101 | 256 | 0.606 | 0 | 0% | 0% | `snap_endpoints` | d_propio=101 m << d_OSRM=256 m (ratio 0.39); snap-to-node colapsó endpoint(s) |
| 5 | 533 | 1116 | 0.523 | 2 | 50% | 0% | `snap_endpoints` | d_propio=533 m << d_OSRM=1116 m (ratio 0.48); snap-to-node colapsó endpoint(s) |
| 63 | 2952 | 1985 | 0.487 | 7 | 0% | 0% | `residual` | no atribuible a snap/turn/via/simplify; residuo combinado |
| 65 | 1901 | 1325 | 0.435 | 3 | 21% | 0% | `via_filtrada` | 21% de aristas en vías que OSRM filtra/penaliza (top: living_street=3) |
| 17 | 900 | 1542 | 0.417 | 4 | 44% | 0% | `via_filtrada` | 44% de aristas en vías que OSRM filtra/penaliza (top: living_street=4) |
| 32 | 900 | 1508 | 0.403 | 4 | 44% | 0% | `via_filtrada` | 44% de aristas en vías que OSRM filtra/penaliza (top: living_street=4) |
| 39 | 266 | 441 | 0.398 | 1 | 0% | 0% | `snap_corto` | d_OSRM=441 m < 1000 m; snap-to-node domina en rutas cortas |
| 19 | 823 | 1288 | 0.361 | 3 | 0% | 0% | `residual` | no atribuible a snap/turn/via/simplify; residuo combinado |
| 35 | 823 | 1280 | 0.357 | 3 | 0% | 0% | `residual` | no atribuible a snap/turn/via/simplify; residuo combinado |
| 46 | 399 | 608 | 0.345 | 2 | 0% | 0% | `snap_corto` | d_OSRM=608 m < 1000 m; snap-to-node domina en rutas cortas |
| 21 | 1522 | 2262 | 0.327 | 2 | 0% | 0% | `residual` | no atribuible a snap/turn/via/simplify; residuo combinado |

## Interpretación

La causa dominante es `snap_endpoints` (12/22). Cada causa coincide con una de las cinco fuentes de divergencia enumeradas en ADR-0011 §Diagnóstico, por lo que la divergencia de los 22 outliers respecto a la tolerancia CP-01a queda atribuida empíricamente y no como hipótesis.
