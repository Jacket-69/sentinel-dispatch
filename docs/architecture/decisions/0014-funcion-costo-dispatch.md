---
adr: 0014
title: Función de costo del despacho — fórmula, tabla de penalización y separación dominio/aplicación
status: accepted
date: 2026-05-19
deciders: Benjamín López
tags: [adr, dominio, dispatch, srs, h3, idoneidad]
---

# ADR 0014 — Función de costo del despacho: fórmula, tabla de penalización y separación dominio/aplicación

## Contexto

H3 (deadline 2026-06-28) implementa el módulo `domain/dispatch/`, responsable de calcular la función de costo que ordena las unidades candidatas para un incidente dado. Al inicio de H3, el paquete estaba vacío; `domain/incidente/` ya existe con las entidades y la validación de coordenadas (ADR-0012, PR #6).

El SRS sec. 2.6-C define la función de costo como:

```
Costo(u, i) = α · T_viaje(u → i) + β · Penalización_Idoneidad(u, i)
```

con α = 1.0 (adimensional) y β = 600 s (segundos por unidad de penalización), y detalla una tabla de penalización (SRS tabla 2.6-C-1) que cubre las 10 combinaciones posibles: 5 categorías MPDS (Alpha, Bravo, Charlie, Delta, Echo) × 2 tipos de unidad (Básica, Avanzada).

Dos reglas de negocio del SRS sec. 2.7 afectan al módulo de despacho:

- **RN-02**: cuando la única unidad Disponible para un incidente Echo/Delta es de tipo Básica, el sistema **no bloquea** — despacha igual pero registra `despacho_suboptimo: true` en el log.
- **RN-04**: unidades en estado Taller quedan excluidas de cualquier cálculo de costo sin excepción.

La pregunta de diseño es triple: ¿dónde vive la fórmula?, ¿cómo se modela la tabla?, ¿y cómo se separa la lógica de costo puro (dominio) de la política de fallback RN-02 (application)?

## Decisión

Las decisiones D1–D6 se toman de forma conjunta porque se refuerzan mutuamente.

**D1 — La fórmula vive en `domain/dispatch/funcion_costo.py` como función pura.**
Se exporta `costo(unidad, incidente, t_viaje_s: float) -> CostoDespacho`. Las constantes `ALPHA` y `BETA_S` se declaran como `Final[float]` en el mismo módulo, alineadas con los valores del SRS y visibles para la defensa GCS. El módulo no importa nada de `adapters/` ni de `application/` — cumple el mandato de ADR-0006 (Ports & Adapters liviano).

**D2 — La tabla de penalización es un dict exhaustivo de 10 entradas.**
Se declara como `TABLA_PENALIZACION_IDONEIDAD: Final[dict[tuple[CategoriaMPDS, TipoUnidad], float]]` con todas las combinaciones enumeradas explícitamente. Los valores relevantes son:

| Categoría MPDS | Unidad Básica | Unidad Avanzada |
|---|---:|---:|
| Alpha | 0.0 | 0.0 |
| Bravo | 0.0 | 0.0 |
| Charlie | 1.0 | 0.0 |
| Delta | `math.inf` | 0.0 |
| Echo | `math.inf` | 0.0 |

El lookup falla con `KeyError` ante cualquier combinación no existente, lo que actúa como defensa anti-drift: si en el futuro se agregan categorías MPDS o tipos de unidad sin actualizar la tabla, el fallo es ruidoso e inmediato, no silencioso.

**D3 — `T_viaje` entra como parámetro `float`, no como port `GrafoVial`.**
La función `costo` recibe `t_viaje_s: float` ya calculado por el caller. Esta decisión desacopla el dominio de dispatch de todo conocimiento sobre routing: el módulo no importa `ports.py` ni `adapters/`, y sus tests unitarios no necesitan levantar grafo. La orquestación del pipeline snap → A* → costo queda en `application/`, que es su lugar natural.

**D4 — La fórmula retorna `math.inf` para Echo/Delta + Básica de forma incondicional. El fallback RN-02 vive en `application/`.**
Separar la *idoneidad médica* (dominio) de la *política operativa ante escasez* (application) permite que la defensa GCS audite ambas lógicas de forma independiente. Si el comité médico cambia las categorías de idoneidad, se toca solo el dominio. Si la política de despacho subóptimo cambia (p. ej. alertar al médico en vez de solo loguear), se toca solo el application. La regla RN-02 queda diferida a ADR-0015.

**D5 — La función retorna `CostoDespacho` (value object con desglose), no un `float` plano.**
El objeto contiene `(valor_total_s, t_viaje_s, penalizacion, es_infinito)`. La motivación viene del requisito de log JSONL append-only (RF-06, ADR-0007): el log de despacho debe persistir el desglose para auditoría posterior. El campo `es_infinito` se cachea como booleano para evitar comparar `float('inf')` en el argmin del application layer.

**D6 — Excepciones de dominio explícitas: `UnidadInelegibleError` y `TViajeInvalidoError`.**
Ambas son subclases de `ValueError`. `UnidadInelegibleError` se lanza cuando la unidad está en estado Taller (RN-04 — el application layer debe filtrarlas antes de llamar a `costo`, pero si no lo hace el fallo es ruidoso). `TViajeInvalidoError` se lanza cuando `t_viaje_s` es NaN o negativo. El principio es "fail loud": un olvido en el application layer nunca debe producir un costo silenciosamente incorrecto.

## Consecuencias

**Positivas:**

- CP-04 (Charlie + Básica vs Avanzada lejana) y CP-05 (Echo + Básica → ∞) son verificables como tests unitarios sin levantar grafo ni base de datos, lo que acelera el ciclo de desarrollo de H3 y reduce la fragilidad de los tests.
- La fórmula y la tabla de penalización quedan documentadas simultáneamente en el SRS, en este ADR y como código con constantes nombradas — la trinchera SRS/ADR/código es defendible ante el GCS sin ambigüedad.
- El dominio queda preparado para PR #9 (selección argmin sobre la lista de costos) y PR #10 (application layer + fallback RN-02), que consumen `CostoDespacho` sin redefinir nada.

**Negativas / costos:**

- Al recibir `t_viaje_s` como input, la función `costo` no puede detectar si el valor proviene de un cálculo errado (p. ej. A* sobre grafo desactualizado). Solo valida NaN y negativos. Mitigación: smoke tests en `application/` que arrancan desde coordenadas reales del dataset y verifican que el tiempo calculado cae en un rango plausible para la IV Región.
- La tabla literal de 10 entradas requiere mantenimiento manual si el SRS evoluciona. Mitigación: el lookup con `KeyError` garantiza que cualquier expansión de los enums que no actualice la tabla falle de inmediato en tiempo de ejecución, no silenciosamente.

**Neutrales:**

- `CostoDespacho` como dataclass de 4 campos agrega overhead mínimo frente a un `float` plano. El argmin en el application layer opera sobre `valor_total_s` directamente, sin penalización algorítmica.

## Trazabilidad

- RF-04 (función de costo multiobjetivo, SRS sec. 2.5) → `domain/dispatch/funcion_costo.py::costo`.
- RN-04 (unidades en Taller excluidas, SRS sec. 2.7) → `UnidadInelegibleError` lanzada en `costo()`.
- CP-04 (Charlie + Básica vs Avanzada lejana) → `tests/unit/domain/dispatch/test_funcion_costo.py::TestCostoReglaDeNegocio::test_cp04_*`.
- CP-05 (Echo + Básica → ∞) → `tests/unit/domain/dispatch/test_funcion_costo.py::TestCostoReglaDeNegocio::test_cp05_*`.
- RN-02 (despacho_suboptimo) → diferido a ADR-0015 + `application/`.

## Referencias

- SRS sec. 2.6-C — fórmula del costo y tabla 2.6-C-1.
- SRS sec. 2.7 — RN-02, RN-04.
- SRS sec. 2.13 — CP-04, CP-05.
- [ADR-0006 — Ports & Adapters liviano](0006-arquitectura-hexagonal-liviana.md) — fundamento de D1 y D3.
- [ADR-0007 — Persistencia JSONL append-only](0007-persistencia-jsonl-append-only.md) — motivación de D5 (desglose para log).
- [ADR-0009 — Refinamiento del árbol MPDS](0009-refinamiento-arbol-mpds.md) — origen de las 5 categorías Alpha..Echo.
- ADR-0015 (próximo, PR siguiente) — política de fallback RN-02 (despacho_suboptimo).
- Matriz de trazabilidad: `docs/quality/trazabilidad.md` filas RF-04 / RN-04.
