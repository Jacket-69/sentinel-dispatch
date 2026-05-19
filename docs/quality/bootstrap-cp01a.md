# Bootstrap CP-01a — estabilidad estadística del conteo 78/100

Cuantifica la afirmación del ADR-0011 §V/L#5 *CP-01a se cumple por margen estrecho (78/100 vs mínimo 75/100)* mediante un bootstrap no paramétrico sobre los 100 errores relativos del fixture `tests/fixtures/osrm_oracle.json`.

## Metodología

- **Muestra original**: 100 pares (idéntico al test IT-01).
- **Estadístico**: `dentro_de_tolerancia(err_rel ≤ 0.30)` → conteo entero en `[0, 100]`.
- **Bootstrap**: 1000 réplicas, muestreo con reemplazo, tamaño igual al original (100).
- **Semilla**: `random.Random(2026)` — el resultado es determinista y reproducible.
- **Criterio CP-01a**: ≥ 75 de 100 pares dentro de tolerancia.

## Resultados

| métrica | valor |
|---|---:|
| Conteo real (sin bootstrap) | **78 / 100** |
| Mediana bootstrap | 78.0 |
| Media bootstrap | 77.86 |
| Desviación estándar | 4.22 |
| IC95 (p2.5, p97.5) | **[69, 86]** |
| Rango (min, max) | [64, 90] |
| % réplicas con conteo ≥ 75 | **78.9%** |

## Interpretación

**IC95 inferior = 69 < 75 → el margen 78/100 es estrecho.** No se puede afirmar que el 95% de las réplicas cumple. La limitación queda cuantificada en ADR-0011 §V/L#5 (no resuelta: el bootstrap no inventa muestras nuevas, sólo cuantifica la variabilidad del fixture disponible).

Adicionalmente, el **78.9%** de las 1000 réplicas bootstrap obtuvieron un conteo ≥ 75, lo que es una estimación directa de la probabilidad de que una repetición del experimento (con el mismo proceso generador del jitter y el mismo grafo) cumpla CP-01a.

## Limitaciones del bootstrap

El bootstrap no paramétrico asume que los 100 pares del fixture son intercambiables y representativos del proceso generador subyacente. Esta hipótesis es razonable porque el jitter es uniforme y la semilla determinista (ADR-0011 §Cómo se generan los pares), pero **no captura sesgos sistemáticos** como el documentado en V/L#3 (sesgo hacia rutas urbanas cortas por radio de jitter pequeño). El IC95 mide variabilidad muestral dada esa distribución, no validez externa frente a una distribución diferente de orígenes/destinos.

Regenerar con `uv run --project core-python python tools/bootstrap_cp01a.py --n-bootstrap 1000 --seed 2026`.
