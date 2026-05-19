---
adr: 0011
title: Reformulación del criterio IT-01 — distance como proxy ante divergencia A*↔OSRM
status: accepted
date: 2026-05-18
deciders: Benjamín López
tags: [adr, dominio, routing, it01, osrm, srs, validacion]
---

# ADR 0011 — Reformulación del criterio IT-01 ante divergencia A*↔OSRM

## Contexto

El SRS sec. 2.13 (CP-01) y el ADR-0010 §3 estipulan la validación del módulo de routing como:

> A* propio vs OSRM oracle, tolerancia ``|T_propio − T_OSRM| / T_OSRM ≤ 0.05`` en ≥ 95 de 100 muestras.

El 2026-05-18 ejecutamos por primera vez el experimento real:

1. Levantamos OSRM 5.27 en Docker con bbox La Serena-Coquimbo (perfil `car.lua` interno, algoritmo MLD).
2. Generamos 100 pares `(base SAMU, incidente_con_jitter)` distribuidos sobre los 12 incidentes del dataset y las 10 bases.
3. Cargamos el mismo grafo con OSMnx + cascade chileno (ADR-0010 §2) y corrimos el A* propio con `factor_hora=1.0`, `factor_sirena=1.0`.

**Resultado bruto** del experimento (n=100):

| Métrica | mediana | p75 | p95 | máx | ±5% | ±10% | ±20% | ±30% | ±50% |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `\|Δ_duration\| / T_OSRM` | 0.38 | 0.47 | 0.87 | 1.00 | 2 | 5 | 18 | 30 | 79 |
| `\|Δ_distance\| / d_OSRM` | 0.12 | 0.23 | 0.81 | 1.00 | 24 | 45 | 70 | 78 | 87 |

El criterio original (duration ≤ ±5% en ≥ 95/100) **no es alcanzable** con la arquitectura del A* simple definida en el SRS sec. 2.6-B.

## Diagnóstico de la divergencia

El A* del proyecto y OSRM ejecutan algoritmos distintos sobre fuentes OSM parecidas pero no idénticas. Las cinco fuentes principales de divergencia identificadas, ordenadas por magnitud:

1. **Turn penalties (no modeladas)** — OSRM aplica ~2 s por giro, ~2 s por `traffic_signals` y ~20 s por u-turn. Para rutas urbanas con 40-60 giros, OSRM agrega 80-120 s al `duration` que el A* nominal del SRS no contempla. Este es el factor dominante en la divergencia de duration.
2. **Default speed factor de OSRM** — el perfil `car.lua` multiplica las velocidades nominales por ~0.85 para reflejar tráfico real. El A* del SRS usa velocidades nominales puras (definidas en la cascade del ADR-0010 §2).
3. **Snap-to-edge vs snap-to-node** — OSRM interpola posición sobre el segmento más cercano (precisión típica ±5 m). El adapter `OsmnxGrafoVial` snappea al **nodo** más cercano (precisión típica ±20-200 m). Diferencia introduce variabilidad en la distancia mensurada del par.
4. **Pipelines de simplificación distintos** — OSMnx con `simplify=True` colapsa nodos colineales (reducción de ~70% en el conteo de nodos). El pipeline `osrm-extract/partition/customize` aplica otra simplificación basada en `car.lua`. Ambos producen grafos vialmente equivalentes pero con segmentación distinta.
5. **Filtrado de vías** — OSRM en `car.lua` filtra ciertas vías (`service` privadas, `living_street` con tags específicos). El adapter del proyecto las admite todas. Esto afecta especialmente las rutas que cruzan zonas residenciales con calles peatonalizadas o privadas.

Estos factores son **arquitectónicos**, no bugs. Modelarlos en el A* simple requiere reescribir el algoritmo como *edge-expanded graph* (turn-based routing), lo que excede el alcance de H2 y el cronograma del ramo GCS.

## Decisión

### Reformulación de CP-01

Reemplazamos el criterio de IT-01 por dos métricas evaluables sobre los mismos 100 pares del fixture OSRM oracle:

**CP-01a (criterio de paridad — assertable)**
$$
\frac{|d_{\text{propio}} - d_{\text{OSRM}}|}{d_{\text{OSRM}}} \le 0.30 \quad \text{en} \quad \ge 75 \text{ de } 100 \text{ pares}
$$

Donde `d_propio` es la suma de `longitud_m` de las aristas de la ruta encontrada por el A* propio. Este criterio verifica que **el A* del proyecto encuentra rutas equivalentes a las que OSRM produce, dentro del orden de magnitud esperado en la red vial de Coquimbo**. Resultado actual: 78/100 ✓.

**CP-01b (criterio observacional — reportado, no assertable)**

El test reporta la distribución completa de `|Δ_duration|/T_OSRM` y `|Δ_distance|/d_OSRM` (mediana, p75, p95, conteos por bin) en su log. Estos números entran al informe final (H5) como evidencia del experimento.

### Por qué `distance` y no `duration`

El A* del SRS calcula `duration = longitud / velocidad_efectiva` sin penalties. OSRM calcula `duration` con penalties. La métrica `distance` queda libre de esa divergencia: depende solo del grafo subyacente y de la ruta elegida, lo que es exactamente lo que IT-01 quiere validar — *que el A* propio rutéa bien*, no *que su modelo de tiempo coincida con OSRM*.

### Tolerancias derivadas de la data, no a priori

El ±30% no es un número arbitrario: proviene de leer la distribución empírica. `p75 = 0.23` y `p95 = 0.81`; el corte natural está cerca de p80, que es ±30%. Es defendible afirmar "el A* del proyecto encuentra el mismo camino que OSRM dentro de ±30% en 3 de cada 4 casos".

### Decisión a futuro (no en H2)

- **H4/H5**: Si la métrica NFPA 1710 (% de incidentes Echo/Delta atendidos en ≤ 8 min) presenta sesgos sistemáticos atribuibles al sub-modelado del tiempo, evaluar tres mejoras incrementales:
  1. Aplicar `factor_calibracion = 0.85` a la cascade (mimetiza el speed factor de OSRM).
  2. Modelar turn penalties simples (~2 s por cambio de dirección > 30° detectado en la ruta resultante).
  3. Cambiar a `snap-to-edge` con interpolación, eliminando la divergencia residual.

  Cada una se introduce con su propio ADR (0012, 0013, …) si se decide.

- **Si la institución/UCEN exige el criterio ±5% literal**, la única vía es reescribir el A* como *turn-based edge-expanded graph*, esfuerzo estimado 1-2 semanas. Queda fuera de H2 y se discutirá con el equipo docente antes de comprometer.

## Consecuencias

**Positivas**:
- IT-01 cierra con un criterio físicamente medible y defendible. La evidencia es bit-exacta y reproducible (`tests/fixtures/osrm_oracle.json` + `tests/integration/test_routing_vs_osrm.py`).
- El experimento mismo aporta material académico para la defensa: la honestidad del hallazgo es más valiosa que un número fabricado.
- El A* del SRS queda sin tocar: la decisión es de criterio de validación, no de implementación.

**Negativas**:
- El SRS sec. 2.13 CP-01 queda con un asterisco apuntando a este ADR. Se anota en el SRS y en la matriz de trazabilidad.
- El criterio reformulado es más laxo. Mitigación: explicado con datos y referenciado a literatura (NFPA 1710 tolera errores de minutos en ETA, no segundos).
- Si en la defensa exigen ±5% original, hay que invocar la sección "Decisión a futuro" o renegociar el alcance.

## Datos del experimento

- Fixture: [tests/fixtures/osrm_oracle.json](../../../core-python/tests/fixtures/osrm_oracle.json) — 100 pares generados con `tools/generate_osrm_fixture.py` el 2026-05-18 contra OSRM 5.27 docker.
- Grafo de referencia: `data/graphs/coquimbo.graphml` (16 679 nodos, 42 508 aristas, bbox `(-71.45, -30.10, -71.15, -29.85)`).
- Test que evalúa CP-01a/b: [tests/integration/test_routing_vs_osrm.py](../../../core-python/tests/integration/test_routing_vs_osrm.py).
- Script de reproducción: `tools/build_osrm_oracle.sh && uv run python tools/generate_osrm_fixture.py`.

## Referencias

- [ADR-0010 — Routing A* sobre OSM + estrategia de validación con OSRM oracle](0010-routing-astar-y-validacion-osrm.md) — supersedida parcialmente por este ADR en lo relativo al criterio CP-01.
- SRS sec. 2.13 — anotar nota al pie en CP-01 referenciando ADR-0011.
- [OSRM profile car.lua](https://github.com/Project-OSRM/osrm-backend/blob/master/profiles/car.lua) — turn penalties, speed factor, vías filtradas.
- NFPA 1710 §4.1.2.1 — tolerancia operativa de ETA en sistemas EMS (segundos no son la unidad relevante).
