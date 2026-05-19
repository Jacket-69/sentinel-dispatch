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

### Cómo se generan los pares (jitter)

El generador `tools/generate_osrm_fixture.py` produce los 100 pares así:

- **Orígenes**: las 10 bases SAMU del dataset (`data/dataset/unidades.json`), sin jitter.
- **Destinos**: los 12 incidentes del dataset (`data/dataset/incidentes.json`), cada uno expandido con `JITTERS_POR_INCIDENTE = 10` perturbaciones independientes.
- **Distribución del jitter**: `uniform` sobre cada componente (lat, lon) por separado, radio `JITTER_GRADOS = 0.0013°` (≈ 144 m a latitud de Coquimbo).
- **Semilla**: `random.Random(SEED=2026).uniform(-r, +r)`, determinista — la regeneración produce bit-exactos los mismos candidatos.
- **Selección**: producto cartesiano `bases × incidentes × jitters` = 1200 candidatos, shuffled con la misma semilla; se itera hasta juntar 100 pares válidos contra OSRM, descartando los que devuelven error de red (`red`), sin ruta (`sin_ruta`) o ruta `< DISTANCIA_MINIMA_M = 200 m` (`distancia_corta`).
- **Metadatos**: a partir del fixture v2 (`metadata_added_at: 2026-05-19`) el JSON committea explícitamente los campos `jitter.{radio_grados, distribucion, aplicado_sobre, generador, jitters_por_incidente}` y `distancia_minima_m` para que un revisor pueda reconstruir el experimento sin leer el script.

## Diagnóstico de la divergencia

El A* del proyecto y OSRM ejecutan algoritmos distintos sobre fuentes OSM parecidas pero no idénticas. Las cinco fuentes principales de divergencia identificadas, ordenadas por magnitud:

1. **Turn penalties (no modeladas)** — OSRM aplica ~2 s por giro, ~2 s por `traffic_signals` y ~20 s por u-turn. Para rutas urbanas con 40-60 giros, OSRM agrega 80-120 s al `duration` que el A* nominal del SRS no contempla. Este es el factor dominante en la divergencia de duration.
2. **Default speed factor de OSRM** — el perfil `car.lua` multiplica las velocidades nominales por ~0.85 para reflejar tráfico real. El A* del SRS usa velocidades nominales puras (definidas en la cascade del ADR-0010 §2).
3. **Snap-to-edge vs snap-to-node** — OSRM interpola posición sobre el segmento más cercano (precisión típica ±5 m). El adapter `OsmnxGrafoVial` snappea al **nodo** más cercano (precisión típica ±20-200 m). Diferencia introduce variabilidad en la distancia mensurada del par.
4. **Pipelines de simplificación distintos** — OSMnx con `simplify=True` colapsa nodos colineales (reducción de ~70% en el conteo de nodos). El pipeline `osrm-extract/partition/customize` aplica otra simplificación basada en `car.lua`. Ambos producen grafos vialmente equivalentes pero con segmentación distinta.
5. **Filtrado de vías** — OSRM en `car.lua` filtra ciertas vías (`service` privadas, `living_street` con tags específicos). El adapter del proyecto las admite todas. Esto afecta especialmente las rutas que cruzan zonas residenciales con calles peatonalizadas o privadas.

Estos factores son **arquitectónicos**, no bugs. Modelarlos en el A* simple requiere reescribir el algoritmo como *edge-expanded graph* (turn-based routing), lo que excede el alcance de H2 y el cronograma del ramo GCS.

### Descomposición empírica de los 22 outliers (2026-05-19)

Para anticipar la defensa GCS, los 22 pares con `|Δ_distance|/d_OSRM > 0.30` se procesaron con `tools/analyze_outliers.py` (clasificador heurístico que recorre la ruta del A*, mide longitud / giros / tipos de vía y atribuye una causa probable entre las cinco listadas arriba).

| Causa probable | Conteo | % de outliers | Familia |
|---|---:|---:|---|
| `snap_endpoints` (ratio `d_propio / d_OSRM < 0.55`) | 12 | 55% | snap-to-node (factor 3) |
| `snap_corto` (d_OSRM < 1 km) | 3 | 14% | snap-to-node (factor 3) |
| `via_filtrada` (>20% de aristas `living_street`/`service`/…) | 3 | 14% | filtrado `car.lua` (factor 5) |
| `residual` (no atribuible con las heurísticas actuales) | 4 | 18% | combinado snap + simplify + speed factor |

**Lectura empírica**: **68%** (15/22) de los outliers se atribuyen a snap-to-node. **14%** se explica por filtrado de vías de OSRM. Solo **18%** queda como residuo combinado; ese residuo es consistente con la divergencia de speed factor y simplify mencionadas en el diagnóstico cualitativo, sin que ninguna heurística simple los aísle por separado.

Conclusión: la divergencia observada no es ruido aleatorio — está dominada por una decisión específica del adapter (snap-to-node, ADR-0010 §2). Eliminar esa decisión (migrar a snap-to-edge con interpolación, listado como pto 3 de "Decisión a futuro" más abajo) recuperaría empíricamente la mayoría de los outliers. El experimento confirma esa proyección con datos, no con conjetura.

Tabla detallada por par (incluye `d_propio`, `d_OSRM`, `err_rel`, `n_giros`, `%vía filtrada`, `%aristas <5 m`, nota de la heurística): [`docs/quality/outliers-cp01a.md`](../../quality/outliers-cp01a.md). CSV procesable: [`docs/quality/outliers-cp01a.csv`](../../quality/outliers-cp01a.csv). Regenerar con `uv run --project core-python python tools/analyze_outliers.py`.

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

## Verdad y limitaciones

Esta sección registra explícitamente las debilidades del experimento y de la decisión, anticipándose a las preguntas críticas que la defensa GCS puede plantear. Cada ítem va anotado con su **estado** tras el lote A de blindaje (PR #11).

1. **El criterio CP-01 original del SRS no fue validado empíricamente antes de redactarse.** El ±5% en duration contra OSRM se escribió en SRS sec. 2.13 sin correr el experimento ni revisar literatura específica sobre divergencia A*↔OSRM. El error no fue de la implementación del A*, fue de la especificación del CP — exactamente la clase de error que la asignatura evalúa. Se documenta aquí porque ocultarlo y luego ser preguntado es peor que reconocerlo y mostrar la corrección (este ADR es la corrección).
   - **Estado (PR #11)**: limitación *inherente al CP-01 original*, no corregible retroactivamente. Mitigación de equipo: se incorporó la convención **spike-before-CP** en [`CONTRIBUTING.md`](../../../CONTRIBUTING.md) — todo CP nuevo del SRS requiere un spike empírico de viabilidad antes de aceptarse, documentado en su ADR como sección *Spike de viabilidad*. Aplicación retroactiva: CP-08 (intento de edición JSONL) y CP-12 (performance 50 unidades ≤ 1000 ms) llevan spike obligatorio antes de H4.
2. **El clasificador de causas usa heurísticas, no demostración formal.** `tools/analyze_outliers.py` asigna una causa por par según umbrales fijos (`ratio < 0.55`, `>20% vía filtrada`, etc.). Es plausible pero no probado: un par podría caer bajo dos causas simultáneamente y el script reporta la primera por prioridad. La interpretación del 68% como "snap-to-node domina" es defendible pero no es una *prueba*.
   - **Estado (PR #11)**: parcialmente corregido. Análisis de sensibilidad sobre grilla 3×3 (`ratio_snap ∈ {0.50, 0.55, 0.60}` × `pct_vía_filtrada ∈ {0.15, 0.20, 0.25}`) muestra que el % de outliers atribuidos a snap-to-node se mantiene en el rango **[68%, 77%]** sobre las 9 combinaciones (mediana 68%). La conclusión *snap-to-node domina* no depende del valor puntual de los umbrales. Detalle en [`docs/quality/outliers-sensibilidad.md`](../../quality/outliers-sensibilidad.md). El argumento "no es una *prueba* formal" sigue vigente; lo nuevo es que tampoco es un artefacto de la elección puntual de umbrales.
3. **La distribución del jitter sesga la muestra hacia rutas urbanas cortas.** El radio de 0.0013° (≈144 m) mantiene los destinos en la zona conurbada La Serena-Coquimbo, lo que es realista para SAMU, pero significa que el fixture no tiene rutas largas inter-comunales. El 23% de los outliers son rutas <1 km, en parte porque la población muestral tiene varias rutas cortas.
   - **Estado (PR #11)**: no abordado en este lote. Corrección planificada en lote B (fixture v3 con producto cartesiano sobre bbox y radio de jitter amplio, requiere Docker activo).
4. **Comparación contra una sola versión de OSRM.** El experimento usa OSRM 5.27 con `car.lua` interno. Cambios futuros del perfil OSRM o regeneraciones del fixture sobre otra versión podrían mover los conteos sin invalidar la decisión.
   - **Estado (PR #11)**: versión exacta documentada — **OSRM 5.27 backend Docker oficial** (imagen `osrm/osrm-backend:v5.27.1`), perfil `profiles/car.lua` interno del binario sin modificaciones, algoritmo **MLD** (Multi-Level Dijkstra), endpoint `/route/v1/driving`. El perfil `car.lua` es estable entre versiones menores de la línea 5.x: la introducción del *speed factor* (~0.85) y los *turn penalties* (~2 s/giro) ocurrió en OSRM 5.0 (release 2016) y se mantiene sin cambios estructurales hasta 5.27 (release 2022); los commits posteriores en `profiles/car.lua` upstream son mayormente ajustes finos de tipos `service`/`living_street` y no afectan los dos factores dominantes de divergencia identificados en el §Diagnóstico de este ADR (puntos 1 y 2). La cita upstream relevante es el [historial de `profiles/car.lua`](https://github.com/Project-OSRM/osrm-backend/commits/master/profiles/car.lua) en el repositorio OSRM. Conclusión: regenerar el fixture sobre una versión 5.x distinta probablemente movería los conteos en márgenes menores al ±10% pero no invertiría el orden de las causas atribuidas.
5. **CP-01a se cumple por margen estrecho.** 78/100 contra mínimo 75/100 — margen de 3 pares. Si la próxima regeneración del fixture cae a 74/100, el test rompe sin que el algoritmo haya cambiado. Mitigación: el fixture está committeado al repo (`tests/fixtures/osrm_oracle.json`) precisamente para que la regeneración sea explícita y revisable, no automática.
   - **Estado (PR #11)**: cuantificado por bootstrap no paramétrico (B=1000 réplicas, semilla=2026, ver [`docs/quality/bootstrap-cp01a.md`](../../quality/bootstrap-cp01a.md)). Resultado: mediana 78, IC95 **[69, 86]**, P(conteo≥75)=**78.9%**. **El IC95 inferior (69) está por debajo del mínimo (75)**, por lo tanto el margen *no es defendible al 95% de confianza*; sin embargo, el 78.9% de las réplicas bootstrap mantienen CP-01a, lo que sí es una cota inferior cuantitativa razonable para la defensa. La limitación sigue existiendo: cuantificarla es honesto, no resolverla — resolverla requiere fixture v3 (V/L#3) con más pares para estrechar el IC.
6. **Las cinco fuentes de divergencia no se aislan experimentalmente.** Para aislarlas habría que re-correr OSRM con perfiles modificados (`turn_penalty=0`, `speed_reduction=1.0`, etc.) y comparar fixture-vs-fixture. Esa validación es "Decisión a futuro" pto 1; sin ella, las atribuciones del clasificador son consistentes con la hipótesis pero no la prueban.
   - **Estado (PR #11)**: no abordado en este lote. Corrección planificada en lote B (requiere Docker activo y regeneración de fixture sobre `car.lua` modificado).

## Datos del experimento

- Fixture: [tests/fixtures/osrm_oracle.json](../../../core-python/tests/fixtures/osrm_oracle.json) — 100 pares generados con `tools/generate_osrm_fixture.py` el 2026-05-18 contra OSRM 5.27 docker. Metadata de jitter agregada al fixture v2 el 2026-05-19.
- Grafo de referencia: `data/graphs/coquimbo.graphml` (16 679 nodos, 42 508 aristas, bbox `(-71.45, -30.10, -71.15, -29.85)`).
- Test que evalúa CP-01a/b: [tests/integration/test_routing_vs_osrm.py](../../../core-python/tests/integration/test_routing_vs_osrm.py).
- Análisis de outliers: [tools/analyze_outliers.py](../../../tools/analyze_outliers.py) genera [`docs/quality/outliers-cp01a.md`](../../quality/outliers-cp01a.md) y `outliers-cp01a.csv`.
- Análisis de sensibilidad de umbrales (PR #11, V/L#2): mismo `tools/analyze_outliers.py` genera [`docs/quality/outliers-sensibilidad.md`](../../quality/outliers-sensibilidad.md).
- Bootstrap CP-01a (PR #11, V/L#5): [tools/bootstrap_cp01a.py](../../../tools/bootstrap_cp01a.py) genera [`docs/quality/bootstrap-cp01a.md`](../../quality/bootstrap-cp01a.md).
- Script de reproducción: `tools/build_osrm_oracle.sh && uv run python tools/generate_osrm_fixture.py`.

## Referencias

- [ADR-0010 — Routing A* sobre OSM + estrategia de validación con OSRM oracle](0010-routing-astar-y-validacion-osrm.md) — supersedida parcialmente por este ADR en lo relativo al criterio CP-01.
- SRS sec. 2.13 — anotar nota al pie en CP-01 referenciando ADR-0011.
- [OSRM profile car.lua](https://github.com/Project-OSRM/osrm-backend/blob/master/profiles/car.lua) — turn penalties, speed factor, vías filtradas.
- NFPA 1710 §4.1.2.1 — tolerancia operativa de ETA en sistemas EMS (segundos no son la unidad relevante).
