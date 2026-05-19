---
adr: 0015
title: Fallback RN-02 — política de despacho sub-óptimo en application
status: accepted
date: 2026-05-19
deciders: Benjamín López
tags: [adr, application, dispatch, srs, h3, rn02, politica-operativa]
---

# ADR 0015 — Fallback RN-02: política de despacho sub-óptimo en application

## Contexto

ADR-0014 (PR #8) estableció que `domain/dispatch/funcion_costo.py` retorna `math.inf` de forma **incondicional** para las combinaciones Echo/Delta + Básica, preservando la pureza de la lógica de idoneidad médica. La regla RN-02 del SRS sec. 2.7 exige, sin embargo, que el sistema nunca bloquee el despacho cuando hay flota disponible:

> "Si la única unidad Disponible es Básica y el incidente es Echo o Delta, el sistema **escala alerta** (despacha igual con flag rojo 'Despacho sub-óptimo crítico — unidad inadecuada') en lugar de bloquear el despacho. El operador puede anular. El evento queda registrado con campo especial `despacho_suboptimo: true` en el log."

PR #9 implementó `seleccionar_unidad`, que opera sobre los costos calculados por el dominio y devuelve `ResultadoSeleccion.elegida = None` cuando todas las unidades disponibles tienen costo ∞. Sin una política explícita de fallback, una flota compuesta íntegramente por unidades Básicas frente a un incidente Echo produciría un rechazo de despacho — comportamiento directamente contrario a RN-02.

Este ADR define dónde y cómo implementar esa política de fallback: en `application/despachar_ambulancia.py::despachar`, como una rama explícita posterior al intento de selección óptima, y anterior a la declaración de saturación (RN-08, CP-10).

## Decisión

Las decisiones D1–D6 se toman de forma conjunta; cada una blinda un vector de fallo distinto.

**D1 — El fallback vive en `application/despachar_ambulancia.py`, en una función auxiliar `_fallback_rn02_basica`.**
La rama se evalúa solo si se cumplen simultáneamente tres condiciones: `seleccion.elegida is None` (el argmin falló), existe al menos una unidad en estado Disponible (distingue "sin flota libre" de "flota libre pero no idónea"), y `incidente.categoria_mpds ∈ _CATEGORIAS_CRITICAS_RN02`. Colocar el fallback en `application/` ejecuta exactamente la separación que ADR-0014 D4 prometió: el dominio solo habla de idoneidad médica, el application orquesta la política operativa. Ningún archivo de `domain/` necesita cambiar.

**D2 — Dentro del fallback, la selección se hace por menor `T_viaje`, no por menor costo formal.**
De las unidades Básicas Disponibles con `T_viaje` finito, se elige la de menor tiempo de viaje. El costo formal de todas ellas es ∞, por lo que no hay criterio de ordenación útil por esa vía; `T_viaje` es el único indicador médico disponible en este escenario de excepción. Los empates se desempatan por `unidad.id` lexicográfico ascendente, criterio idéntico al CP-11 del camino normal, lo que mantiene consistencia de comportamiento ante tests deterministas.

**D3 — El costo reportado en el log se recalcula con `costo(unidad_basica, incidente, t_viaje)`, resultado `math.inf`, y se preserva `t_viaje_s`.**
No se inventa un costo artificial. El objeto `CostoDespacho` resultante tendrá `valor_total_s = math.inf` y `penalizacion = math.inf`, pero `t_viaje_s` estará poblado con el valor real del viaje. El JSONL (RF-06, ADR-0007) registra costo ∞ acompañado del flag `despacho_suboptimo=True`. Esto es deliberado: enmascarar el costo con un valor finito ficticio daría la ilusión de un despacho normal en herramientas estadísticas, ocultando exactamente la información que RN-02 exige visibilizar. Las comparaciones entre despachos sub-óptimos se harán por `t_viaje_s`, no por `valor_total_s`.

**D4 — `ResultadoDespacho.despacho_suboptimo: bool` es un campo dedicado, y `motivo = MotivoDespacho.SUBOPTIMO_RN02` es su complemento legible.**
El flag no se deriva del campo `motivo` en cada lectura del log; se persiste directamente como campo bit-exacto. La tabla siguiente resume los cuatro caminos posibles al declarar un resultado de despacho:

| `MotivoDespacho` | `despacho_suboptimo` | `elegida` | Condición de activación |
|---|:---:|:---:|---|
| `OPTIMO` | `False` | unidad | argmin finito, sin penalización extra |
| `PENALIZADO` | `False` | unidad | argmin finito, penalización > 0 (ej. Charlie + Básica) |
| `SUBOPTIMO_RN02` | `True` | unidad | argmin ∞, Disponibles existen, categoría Echo/Delta |
| `SATURACION` | `False` | `None` | sin Disponibles (RN-08) |

Esta tabla hace explícito que `SUBOPTIMO_RN02` y `SATURACION` son casos ortogonales: el primero implica flota libre pero no idónea; el segundo implica ausencia de flota libre.

**D5 — Cuando el fallback se aplica, el orquestador emite `logging.WARNING` con `unidad.id`, `incidente.id` y `categoria_mpds`.**
El warning queda disponible para sistemas de observabilidad (Prometheus, alertmanager) sin requerir parsear el JSONL. En H4 se añadirá el exportador de métricas (RF-11); hasta entonces, el log de texto es la superficie de auditoría operacional. Un operador de guardia que vea repetidos warnings `SUBOPTIMO_RN02` para la misma zona geográfica tiene señal clara de desbalance de flota.

**D6 — El orden de evaluación es: argmin normal → Disponibles ∧ RN-02 aplica → fallback → saturación.**
Si no hay unidades Disponibles en absoluto, el flujo salta directamente a saturación (RN-08, CP-10) sin tocar el fallback. Esta secuencia evita el caso confundible donde `seleccion.elegida is None` se interpreta como saturación, cuando en realidad hay flota libre. La constante `_CATEGORIAS_CRITICAS_RN02: frozenset[CategoriaMPDS]` contiene `{Echo, Delta}` y centraliza el alcance de RN-02; un cambio futuro es un patch de una línea.

## Consecuencias

**Positivas:**

- RN-02 se cumple literalmente: el sistema nunca rechaza un despacho por idoneidad cuando hay flota Disponible, independientemente de su composición.
- ADR-0014 D4 queda intacta: la fórmula de costo en el dominio nunca tiene ramas condicionales para RN-02. La auditoría GCS puede mostrar `funcion_costo.py` y `despachar_ambulancia.py` como archivos independientes con responsabilidades disjuntas, lo que refuerza el argumento de arquitectura hexagonal.
- CP-05 (Echo + Básica → ∞) sigue siendo un test puro del dominio en `tests/unit/domain/dispatch/test_funcion_costo.py`, sin mención al fallback. El test del orquestador en `tests/unit/application/test_despacho.py` cubre el caso donde el fallback se activa — ambos son ortogonales y no se pisan.

**Negativas / costos:**

- El JSONL de un despacho sub-óptimo contiene `valor_total_s = inf`, lo que confunde herramientas estadísticas que esperan valores finitos. Mitigación: el exportador RF-11 (H4) puede agregar una columna derivada `costo_efectivo` que sustituya `inf` por `t_viaje_s` cuando `despacho_suboptimo` es `True`.
- Si RN-02 evoluciona (p. ej. incluir Charlie + Básica), el cambio toca `_CATEGORIAS_CRITICAS_RN02` en el orquestador. La constante aísla esa decisión y el cambio es de una línea, pero existe el riesgo de olvidar actualizar también los tests de regresión. Mitigación: el nombre `_CATEGORIAS_CRITICAS_RN02` aparece en los docstrings de los tests parametrizados para hacer la referencia cruzada explícita.
- El fallback no considera unidades en estado EnRuta como candidatas, solo Disponibles. Esto es consistente con el texto literal de RN-02 ("la única **Disponible** es Básica"), pero un operador real podría preferir una Avanzada EnRuta cercana sobre una Básica Disponible lejana. Esa decisión queda fuera del SRS v1 y se registra como deuda técnica en `docs/quality/deuda_tecnica.md`.

**Neutrales:**

- La constante `_CATEGORIAS_CRITICAS_RN02: frozenset[CategoriaMPDS]` con `{Echo, Delta}` es el único punto de configuración del fallback. No se introduce ningún flag de feature ni parámetro de entorno.

## Trazabilidad

- RN-02 (SRS sec. 2.7) → `application/despachar_ambulancia.py::_fallback_rn02_basica` + `despachar`.
- RN-08 (SRS sec. 2.7) → `application/saturacion.py::detectar_saturacion` (caso disjunto al fallback RN-02).
- CP-05 (SRS sec. 2.13) → cubierto como test del dominio en `tests/unit/domain/dispatch/test_funcion_costo.py` (sin fallback) y como test del orquestador en `tests/unit/application/test_despacho.py` (con fallback cuando aplica).
- CP-10 (SRS sec. 2.13) → cubierto en `tests/unit/application/test_saturacion.py`.

## Referencias

- SRS sec. 2.7 — RN-02 (texto literal citado en Contexto), RN-04, RN-08.
- SRS sec. 2.13 — CP-05, CP-10.
- [ADR-0006 — Ports & Adapters liviano](0006-arquitectura-hexagonal-liviana.md).
- [ADR-0007 — Persistencia JSONL append-only](0007-persistencia-jsonl-append-only.md) — receptor del campo `despacho_suboptimo`.
- [ADR-0014 — Función de costo del despacho](0014-funcion-costo-dispatch.md) — predecesor inmediato; D4 estableció la separación dominio/aplicación que este ADR ejecuta.
