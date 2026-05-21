---
adr: 0020
title: CP-01c parcial — snap-to-edge necesario en H5 para cerrar el criterio
status: accepted
date: 2026-05-21
deciders: Benjamin López
tags: [adr, routing, calibracion, h4, h5, cp01c]
---

# ADR 0020 — CP-01c parcial: snap-to-edge necesario para cerrar

## Contexto

[ADR-0013](0013-cp01c-criterio-calibrado.md) propuso `CP-01c = duration ±15 % en ≥ 85/100 pares` como objetivo de paridad post-calibración, descomponiéndolo en tres mejoras (factor 0.85, turn penalty, snap-to-edge). El plan original asumía que las dos primeras (H4) serían suficientes y la tercera (H5) era *stretch*.

El experimento H4-cal-eval ejecutado el 2026-05-21 refutó esa hipótesis: aplicando solo las mejoras 1 y 2, el criterio se queda en **27/100 dentro de ±15 %**, con mediana 0.250. La predicción del ADR-0011 ya advertía que el 68 % de los outliers se atribuían a snap-to-node, así que esto es consistente con el análisis previo: sin snap-to-edge, el 68 % de la dispersión no se reduce.

Este ADR cierra formalmente el ciclo de calibración H4 reconociendo que **CP-01c es alcanzable, pero no en H4 — requiere snap-to-edge en H5**.

## Decisión

1. **ADR-0013 sigue `proposed`** (criterio numérico no alcanzado). No se promueve a `accepted` hasta que H5-cal-3 entregue snap-to-edge y se mida sobre el mismo fixture.
2. **CP-01c se cierra empíricamente en H5**, no en H4. La tarea H5-cal-3 del [ADR-0016](0016-camino-95-cp01a.md) §"Ruta A" se vuelve **bloqueante** para `accepted` de ADR-0013.
3. **El criterio CP-01c-strict (±10 % en ≥ 90/100)** queda como objetivo *stretch* dependiente de la fixture v3 N≥300 (Ruta B) — sin compromiso.
4. **Las mejoras 1 y 2 quedan integradas** en el repo (función `cargar_grafo_iv_region(factor_calibracion=...)` y módulo `domain/routing/a_estrella_calibrado.py`). H5-cal-3 las consume; no se rehacen.

### Resultado parcial congelado (corrida 2026-05-21)

| Criterio | Medido | Mínimo CP-01c | Δ |
|---|---|---|---|
| dentro ±15 % | 27/100 | 85/100 | -58 |
| mediana | 0.250 | objetivo ~0.15 | +0.10 |
| dentro ±20 % | 37/100 | — (informativo) | — |
| dentro ±30 % | 65/100 | (CP-01a passing: 78) | — |

**Conclusión empírica**: la calibración movió la curva pero el snap explica ~73 % de la dispersión restante. Sin atacar snap, no se cierra ±15 %.

## Por qué este ADR (separado del 0013)

ADR-0013 quedó como **placeholder de un objetivo**. Marcarlo `accepted` ahora sería falso (el criterio no se cumple); marcarlo `rejected` sería excesivo (el criterio sigue siendo el plan, solo que llega más tarde). Mantenerlo `proposed` con un sub-ADR explicando el delta es la forma honesta:

- ADR-0013 = qué queremos lograr (sigue vigente).
- ADR-0020 = qué medimos y qué falta (este ADR, accepted).

Cuando H5-cal-3 entregue, ADR-0013 pasa a `accepted` con referencia cruzada a ADR-0016 §H5-cal-3.

## Plan H5 (heredado de ADR-0016 Ruta A)

Tareas con esfuerzo estimado (en horas-hombre):

| ID | Tarea | Esfuerzo | Salida |
|---|---|---|---|
| H5-cal-3a | Agregar `coord_a_posicion_en_arista(lat, lon) → PosicionEnArista(arista, fraccion)` al port `GrafoVial` + implementación OSMnx | 3-4 h | Posición interpolada exacta sobre arista, no nodo |
| H5-cal-3b | Adaptar `a_estrella_calibrado` para origen/destino en mitad de arista | 2-3 h | A* con costos parciales por el segmento truncado |
| H5-cal-3c | Re-correr `test_cp01c_calibracion_y_turn_penalty`; si pasa, promover ADR-0013 a `accepted` | 1 h + iteración | Test deja de ser `xfail` |

**Esfuerzo total esperado: 6-8 h.** Cabe holgado en H5 (deadline 2026-07-15) con simulación + informe.

### Decisión arquitectónica anticipada para H5-cal-3a

Cambiar la firma del port `GrafoVial` agregando un método nuevo es decisión costosa (todo adapter debe implementarlo). Alternativas para considerar en H5:

- **(a)** Agregar `coord_a_posicion_en_arista` al port. Pros: explícito, type-safe. Contras: rompe `OsmnxGrafoVial` y cualquier fake de test que implementaba `GrafoVial`.
- **(b)** Helper libre en `domain/routing/snap_to_edge.py` que recibe el grafo y devuelve la posición. Pros: no toca el port. Contras: invierte la dirección de la dependencia respecto a Ports & Adapters.

Recomendación para H5: opción (a) con `Protocol` opcional `GrafoVialConSnapEdge(GrafoVial)` que extiende sin romper el contrato base. Decisión final cuando se inicie H5-cal-3.

## Paridad RT-02 (Java vs Python) tras snap-to-edge

Punto importante: snap-to-edge cambia las rutas que el A* devuelve (los nodos del path pueden diferir marginalmente vs snap-to-node). Si Java no se porta simultáneamente, el job `compare` puede divergir.

**Plan v1**: snap-to-edge **solo en el A* calibrado experimental** (no en el A* operativo). El `run-dataset` operativo sigue usando el A* original sin snap-to-edge. El test CP-01c usa el calibrado. **Resultado**: paridad RT-02 12/12 OK se preserva; CP-01c se cierra en módulo experimental.

Si se quiere snap-to-edge operativo (acerca duration al de OSRM en producción), eso es decisión separada que rompería paridad ±5 % de ADR-0008. No es scope v1.

## Consecuencias

### Positivas

- **CP-01c no queda como promesa vacía**: el plan H5 tiene tareas concretas con esfuerzo estimado.
- **La defensa académica gana coherencia**: "medimos, falló, hicimos análisis empírico de outliers, identificamos snap como responsable mayor, lo dejamos para H5 con plan numérico". Mejor que prometer y entregar sin medir.
- **Las mejoras 1 y 2 quedan capitalizadas** — no se descartan; H5 las consume.

### Negativas / costo

- CP-01c no se cierra en H4 como el plan original asumía. H5 se carga con una tarea adicional de 6-8 h.
- El `xfail` test integration es un recordatorio público de la deuda. Si alguien lo corre con `--runxfail`, falla ruidosamente.

### Neutras

- ADR-0016 §H5-cal-3 sigue siendo el plan vinculante; este ADR sólo eleva su prioridad de "stretch" a "necesario".

## Cumplimiento / verificación

- `core-python/tests/integration/test_routing_vs_osrm.py::test_cp01c_calibracion_y_turn_penalty` marcado `@pytest.mark.xfail(strict=True)` con razón que apunta a este ADR.
- `docs/quality/trazabilidad.md` CP-01c referencia ambos ADRs (0013 y 0020).
- Cuando H5-cal-3c haga pasar el test, **quitar el `xfail` Y promover ADR-0013 a `accepted`** en el mismo PR (atomicidad documental).

## Referencias

- [ADR-0011](0011-reformulacion-criterio-it01.md) — descomposición empírica de outliers que predijo este resultado.
- [ADR-0013](0013-cp01c-criterio-calibrado.md) — placeholder original; sigue `proposed`.
- [ADR-0016](0016-camino-95-cp01a.md) — Ruta A (snap-to-edge) y Ruta B (fixture v3) hacia 95 %.
- `tests/integration/test_routing_vs_osrm.py::test_cp01c_calibracion_y_turn_penalty` — test que mide el delta.
