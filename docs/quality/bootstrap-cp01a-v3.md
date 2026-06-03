# Bootstrap CP-01a — estabilidad estadística del conteo 269/300

Cuantifica la estabilidad estadística del margen 269/300 (mínimo 225/300, ADR-0011 §V/L#5) mediante un bootstrap no paramétrico sobre los 300 errores relativos de un fixture OSRM oracle.

## Metodología

- **Muestra original**: 300 pares (idéntico al test IT-01).
- **Estadístico**: `dentro_de_tolerancia(err_rel ≤ 0.30)` → conteo entero en `[0, 300]`.
- **Bootstrap**: 1000 réplicas, muestreo con reemplazo, tamaño igual al original (300).
- **Semilla**: `random.Random(2026)` — el resultado es determinista y reproducible.
- **Criterio CP-01a**: ≥ 225 de 300 pares dentro de tolerancia.

## Resultados

| métrica | valor |
|---|---:|
| Conteo real (sin bootstrap) | **269 / 300** |
| Mediana bootstrap | 269.0 |
| Media bootstrap | 268.91 |
| Desviación estándar | 5.35 |
| IC95 (p2.5, p97.5) | **[258, 279]** |
| Rango (min, max) | [253, 284] |
| % réplicas con conteo ≥ 225 | **100.0%** |

## Interpretación

**IC95 inferior = 258 ≥ 225 → el margen 269/300 es defendible matemáticamente.** El 95% inferior de las réplicas bootstrap mantiene el cumplimiento de CP-01a.

Adicionalmente, el **100.0%** de las 1000 réplicas bootstrap obtuvieron un conteo ≥ 225, lo que es una estimación directa de la probabilidad de que una repetición del experimento (con el mismo proceso generador del jitter y el mismo grafo) cumpla CP-01a.

## Limitaciones del bootstrap

El bootstrap no paramétrico asume que los 300 pares del fixture son intercambiables y representativos del proceso generador subyacente. Esta hipótesis es razonable porque el jitter es uniforme y la semilla determinista (ADR-0011 §Cómo se generan los pares), pero **no captura sesgos sistemáticos** como el documentado en V/L#3 (sesgo hacia rutas urbanas cortas por radio de jitter pequeño). El IC95 mide variabilidad muestral dada esa distribución, no validez externa frente a una distribución diferente de orígenes/destinos.

Regenerar con `uv run --project core-python python tools/bootstrap_cp01a.py --n-bootstrap 1000 --seed 2026`.
