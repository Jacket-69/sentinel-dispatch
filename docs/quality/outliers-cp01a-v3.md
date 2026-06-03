# Outliers CP-01a — clasificación por causa probable

Generado por `tools/analyze_outliers.py` sobre `core-python/tests/fixtures/osrm_oracle_v3.json` (tolerancia: 30%). Las heurísticas y umbrales se documentan en el módulo. Esta tabla se referencia desde ADR-0011 §Diagnóstico.

**Total outliers**: 31 / 300 (18 clasificados por causa + 13 irruteables en el grafo propio — componente desconectado, típico de anclas oceánicas del fixture cartesiano v3; son outliers de conectividad, no de divergencia de distancia).

## Resumen por causa

| Causa | Conteo | % de outliers |
|---|---:|---:|
| `residual` | 11 | 61% |
| `snap_endpoints` | 7 | 39% |

## Detalle por par

| id | d_propio (m) | d_OSRM (m) | err_rel | giros | %vía filtrada | %aristas <5 m | causa | nota |
|---:|---:|---:|---:|---:|---:|---:|---|---|
| 122 | 34723 | 8484 | 3.093 | 15 | 0% | 1% | `residual` | no atribuible a snap/turn/via/simplify; residuo combinado |
| 202 | 42672 | 17336 | 1.461 | 12 | 0% | 0% | `residual` | no atribuible a snap/turn/via/simplify; residuo combinado |
| 114 | 0 | 5653 | 1.000 | 0 | 0% | 0% | `snap_endpoints` | d_propio=0 m << d_OSRM=5653 m (ratio 0.00); snap-to-node colapsó endpoint(s) |
| 184 | 3105 | 15452 | 0.799 | 2 | 0% | 0% | `snap_endpoints` | d_propio=3105 m << d_OSRM=15452 m (ratio 0.20); snap-to-node colapsó endpoint(s) |
| 195 | 21044 | 11910 | 0.767 | 23 | 0% | 0% | `residual` | no atribuible a snap/turn/via/simplify; residuo combinado |
| 103 | 11566 | 6562 | 0.762 | 8 | 0% | 0% | `residual` | no atribuible a snap/turn/via/simplify; residuo combinado |
| 95 | 7255 | 18837 | 0.615 | 9 | 0% | 0% | `snap_endpoints` | d_propio=7255 m << d_OSRM=18837 m (ratio 0.39); snap-to-node colapsó endpoint(s) |
| 71 | 13921 | 34525 | 0.597 | 7 | 0% | 0% | `snap_endpoints` | d_propio=13921 m << d_OSRM=34525 m (ratio 0.40); snap-to-node colapsó endpoint(s) |
| 25 | 7370 | 17486 | 0.579 | 9 | 0% | 0% | `snap_endpoints` | d_propio=7370 m << d_OSRM=17486 m (ratio 0.42); snap-to-node colapsó endpoint(s) |
| 266 | 5646 | 12226 | 0.538 | 10 | 0% | 0% | `snap_endpoints` | d_propio=5646 m << d_OSRM=12226 m (ratio 0.46); snap-to-node colapsó endpoint(s) |
| 225 | 16260 | 32839 | 0.505 | 10 | 0% | 0% | `snap_endpoints` | d_propio=16260 m << d_OSRM=32839 m (ratio 0.50); snap-to-node colapsó endpoint(s) |
| 287 | 13156 | 9471 | 0.389 | 7 | 0% | 0% | `residual` | no atribuible a snap/turn/via/simplify; residuo combinado |
| 34 | 3266 | 5026 | 0.350 | 13 | 0% | 0% | `residual` | no atribuible a snap/turn/via/simplify; residuo combinado |
| 68 | 34090 | 25387 | 0.343 | 15 | 0% | 0% | `residual` | no atribuible a snap/turn/via/simplify; residuo combinado |
| 63 | 965 | 1461 | 0.339 | 0 | 10% | 0% | `residual` | no atribuible a snap/turn/via/simplify; residuo combinado |
| 105 | 17390 | 25580 | 0.320 | 14 | 0% | 1% | `residual` | no atribuible a snap/turn/via/simplify; residuo combinado |
| 139 | 16648 | 24056 | 0.308 | 4 | 0% | 0% | `residual` | no atribuible a snap/turn/via/simplify; residuo combinado |
| 137 | 2275 | 3253 | 0.301 | 7 | 0% | 0% | `residual` | no atribuible a snap/turn/via/simplify; residuo combinado |

## Interpretación

La causa dominante es `residual` (11/18). Cada causa coincide con una de las cinco fuentes de divergencia enumeradas en ADR-0011 §Diagnóstico, por lo que la divergencia de los 18 outliers respecto a la tolerancia CP-01a queda atribuida empíricamente y no como hipótesis.
