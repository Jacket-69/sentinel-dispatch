---
adr: 0013
title: CP-01c — criterio numérico esperado tras calibración (placeholder H4)
status: proposed
date: 2026-05-19
deciders: Benjamín López
tags: [adr, dominio, routing, it01, osrm, srs, validacion, placeholder]
---

# ADR 0013 — CP-01c, criterio numérico esperado tras calibración

## Contexto

ADR-0011 reformuló CP-01 en dos partes:

- **CP-01a** (assertable): paridad de distancia `|d_propio − d_OSRM| / d_OSRM ≤ 0.30` en ≥ 75/100 pares. Resultado actual: 78/100 ✓.
- **CP-01b** (observacional): distribución de divergencia en duration reportada al log, no asserteable porque OSRM modela turn penalties y speed factor que el A* simple del SRS sec. 2.6-B no contempla.

El experimento empírico del 2026-05-19 (descomposición de outliers en ADR-0011 §Diagnóstico) atribuye **68% de los outliers a snap-to-node**, **14% a filtrado de vías** (`car.lua` filtra `living_street`/`service`), **18% residual** combinado. Si las tres mejoras incrementales listadas en ADR-0011 §"Decisión a futuro" se aplican, el criterio CP-01 debería poder *endurecerse* a un objetivo intermedio entre el ±5% inalcanzable y el ±30% actual.

Este ADR fija ese objetivo intermedio como **CP-01c**, sin implementarlo todavía. Es un placeholder explícito para que la planificación de H4/H5 sepa hacia dónde apuntar y para que la defensa del 2026-05-25 pueda referenciar un compromiso concreto en lugar de hablar genéricamente de "calibración futura".

## Decisión

CP-01c se define como criterio numérico de paridad **post-calibración**, evaluado sobre los mismos 100 pares del fixture `osrm_oracle.json` cuando se completen las mejoras 1 y 2 del ADR-0011 §"Decisión a futuro":

1. Aplicar `factor_calibracion = 0.85` al cascade de velocidades (mimetiza el speed factor de OSRM en `car.lua`).
2. Modelar turn penalties simples (~2 s por cambio de bearing > 30° detectado en la ruta resultante).

Con esas dos mejoras aplicadas, **CP-01c (objetivo)**:

$$
\frac{|T_{\text{propio}} − T_{\text{OSRM}}|}{T_{\text{OSRM}}} \le 0.15 \quad \text{en} \quad \ge 85 \text{ de } 100 \text{ pares}
$$

Es decir, **duration ±15% en ≥ 85/100 pares**. Esto es menos exigente que el ±5% original del SRS pero significativamente más exigente que el ±30% actual y, según el experimento, alcanzable sin migrar a edge-expanded routing.

Si además se implementa la mejora 3 (snap-to-edge con interpolación, elimina el ~68% de outliers atribuidos a snap), el criterio podría apretarse a **CP-01c-strict: ±10% en ≥ 90/100**. Esta variante queda como objetivo *stretch*, no comprometida.

## Cómo se valida

Tres pasos secuenciales, cada uno como sub-PR independiente dentro de H4:

1. **Tarea H4-cal-1** — agregar parámetro `factor_calibracion: float = 1.0` a `cargar_grafo_iv_region` o al adapter; ajustar tests; correr `test_routing_vs_osrm.py` con `factor_calibracion=0.85` y verificar que la distribución de duration mejora (mediana baja de 0.38 hacia 0.15-0.20).
2. **Tarea H4-cal-2** — modelar turn penalties en `domain/routing/a_estrella.py` como término aditivo del costo: por cada par de aristas consecutivas con `|Δ_bearing| > 30°` sumar `2.0` segundos. Requiere refactor menor del A* para pasar la arista previa al expansor de vecinos.
3. **Tarea H4-cal-eval** — re-correr `test_routing_vs_osrm.py` con ambos cambios y assertear CP-01c. Si pasa, marcar este ADR como `status: accepted` y actualizar `docs/quality/trazabilidad.md` RF-03 con la nueva métrica.

Cada paso es un commit/PR separable porque cada uno tiene un efecto medible aislado: la *calibración* y los *turn penalties* mueven la distribución de `duration`, no la de `distance` — CP-01a seguirá pasando si CP-01c pasa.

## Por qué placeholder y no implementación inmediata

- **H2 ya cerró** (PR #5 mergeado 2026-05-18) con CP-01a/b. Reabrir H2 para meter calibración rompe la disciplina de hitos del cronograma académico.
- **La Segunda Evaluación (2026-05-25)** evalúa el estado actual, no el futuro. Un ADR placeholder con criterio numérico es defensa suficiente: "sabemos cuánto deberíamos mejorar y cómo medirlo".
- **H4 (deadline 2026-07-10)** ya incluye "exportador + JSONL log + RT-01..04". Sumar calibración alarga ese hito en ~2-3 días, defendible si la métrica NFPA 1710 del informe final lo justifica.
- **Si el equipo docente exige CP-01c implementado antes del informe final**, este ADR ya tiene el plan de tres pasos listo para ejecutar.

## Consecuencias

**Positivas**:
- Defensa GCS puede responder "¿qué harían con más tiempo?" con un compromiso numérico, no con vaguedades.
- El equipo de desarrollo tiene un objetivo medible y descompuesto en tareas atómicas; H4 puede planificarse contra esto.
- El criterio numérico está derivado de datos del experimento, no a priori — `factor_calibracion=0.85` viene de OSRM `car.lua`, no de un guess.

**Negativas**:
- Es un compromiso público; si en H4 resulta inalcanzable (p. ej. porque la mediana post-calibración cae en 0.18 y no 0.15), hay que abrir un ADR-0014 corrigiendo. Mitigación: el criterio está derivado de la descomposición de outliers, que predice mejoras consistentes con la magnitud propuesta.

**Neutrales**:
- ADR queda en `status: proposed` hasta que H4 lo ejecute. La defensa del 25-may lo cita como "compromiso post-H2", no como hecho consumado.

## Referencias

- [ADR-0011](0011-reformulacion-criterio-it01.md) — Reformulación de CP-01 a CP-01a/b. Este ADR es la continuación natural.
- [ADR-0010](0010-routing-astar-y-validacion-osrm.md) — Cascade de velocidades original (sin `factor_calibracion`).
- [`docs/quality/outliers-cp01a.md`](../../quality/outliers-cp01a.md) — descomposición empírica que predice la mejora esperable.
- SRS sec. 2.13 CP-01 — fuente normativa original (±5% en duration), reformulada por ADR-0011, complementada con compromiso CP-01c por este ADR.
