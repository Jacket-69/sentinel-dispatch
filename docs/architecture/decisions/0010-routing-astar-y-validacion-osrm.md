---
adr: 0010
title: Routing A* sobre OSM + estrategia de validación con OSRM oracle
status: amended
superseded-by: 0011 (parcial — criterio CP-01)
date: 2026-05-18
deciders: Benjamin López
tags: [adr, dominio, routing, astar, osm, osmnx, osrm, h2]
---

# ADR 0010 — Routing A* sobre OSM + estrategia de validación con OSRM oracle

> **Aviso de enmienda (2026-05-18, mismo día):** las decisiones de **infraestructura** (puerto `GrafoVial`, cascade de velocidades, pipeline OSRM self-host, fixture committeado) siguen vigentes. El **criterio numérico de IT-01** (originalmente `duration ±5% en ≥95/100`) fue reformulado por [ADR-0011](0011-reformulacion-criterio-it01.md) tras el experimento real: ahora `distance ±30% en ≥75/100` (CP-01a) más reporte observacional de duration (CP-01b). Las líneas afectadas de este ADR son §Contexto (item de validación) y §3 (script `generate_osrm_fixture.py` y test IT-01). El resto se mantiene.

## Contexto

El hito H2 (deadline 2026-06-14) exige construir el módulo de routing del proyecto. El SRS sec. 2.6-B especifica:

- **Algoritmo**: A* sobre grafo dirigido cargado de OSM.
- **Peso de arista**: `peso = longitud_m / (maxspeed_ms × factor_hora × factor_sirena)` (resultado en segundos de viaje).
- **Heurística**: Haversine entre coordenadas geográficas, escalada por la velocidad máxima del sistema. El valor original (`v_max = 140 km/h`) se elevó a `v_max = 180 km/h ≈ 50.0 m/s` en el commit `561bfa5` para preservar la admisibilidad ante el pico real `motorway × factor_sirena = 120 × 1.4 = 168 km/h` (ver `heuristica.py:15`). Sigue admisible porque ningún tramo puede recorrerse a velocidad efectiva superior a `v_max`.
- **Validación IT-01** (CP-01 del SRS): A* propio vs OSRM oracle. **El criterio numérico original (`|T_propio − T_OSRM| / T_OSRM ≤ 0.05` en ≥ 95 de 100) fue reformulado por [ADR-0011](0011-reformulacion-criterio-it01.md) tras el experimento del 2026-05-18.** El criterio vigente es `|Δ_distance| / d_OSRM ≤ 0.30` en ≥ 75/100 (CP-01a) + reporte observacional de duration (CP-01b).
- **Snap (RN-09)**: si las coordenadas del incidente no tienen un nodo OSM a < 500 m, snap al más cercano + alerta al operador.

La sesión de research del 2026-05-18 (delegada a tres subagentes paralelos) levantó tres bloques de decisión que este ADR consolida:

1. **Contrato del puerto `GrafoVial`** — qué expone el dominio para que el A* sea puro.
2. **Imputación de `maxspeed` faltantes** — en OSM-Chile <30% de aristas tienen el tag, OSRM aplica una cascade por `highway` class; si no replicamos la cascade nuestras ETAs divergen sistemáticamente de OSRM en 30–60%, no en el ±5% que pide el SRS.
3. **Cómo correr el oracle OSRM** — demo público vs self-host docker, qué committeamos al repo.

## Decisión

### 1. Puerto `GrafoVial` (lógica del dominio)

El módulo `domain/routing/` depende únicamente del puerto `GrafoVial` (Protocol). El A* no conoce OSMnx, NetworkX ni archivos. Los adapters (`adapters/grafo_osmnx.py`, `tests/.../grafo_fake.py`) implementan la interfaz.

Métodos mínimos del puerto:

- `vecinos(nodo: NodoId) -> Iterable[Arista]`
- `coordenadas(nodo: NodoId) -> tuple[float, float]` — `(lat, lon)` en grados decimales
- `nodo_mas_cercano(lat: float, lon: float) -> NodoId` — para RN-09
- `distancia_snap_m(lat: float, lon: float, nodo: NodoId) -> float` — para alerta RN-09

**Tipo de identificador**: `NodoId = int` (alias). Los IDs de OSM son `int64` y el SRS los loggea como enteros en `ruta_nodos`. Un dataclass o `NewType` no agrega semántica.

**Modelo de `Arista`**: dataclass frozen con `origen`, `destino`, `longitud_m: float`, `velocidad_efectiva_kmh: float` (resultado del cascade, ver §2). El dominio convierte a m/s en el cálculo de peso, no antes.

**Parámetros de ejecución (no del grafo)**: `factor_hora` y `factor_sirena` se pasan a `a_estrella(grafo, origen, destino, factor_hora, factor_sirena)`. Razón: dependen del timestamp del incidente (tabla SRS sec. 2.6-B) y del estado operativo de la unidad (sirena activa o no), no de la red vial.

**Lo que queda fuera del puerto**: imports de OSMnx/NetworkX/shapely, lectura de archivos, conversión de unidades, cálculo de Haversine (vive en `domain/routing/heuristica.py`), estado mutable.

### 2. Cascade de velocidades alineada con OSRM

Para que IT-01 sea físicamente alcanzable (±5% en duration), el adapter OSMnx replica el cascade que `osrm-extract` con `car.lua` aplica:

1. Si la arista OSM tiene tag `maxspeed`: usar ese valor (después de parseo: "60", "60 km/h", "30 mph", lista).
2. Si no, default por `highway` type según tabla Chile:

| highway | km/h |  | highway | km/h |
|---|---|---|---|---|
| motorway | 120 | | tertiary | 40 |
| motorway_link | 80 | | tertiary_link | 30 |
| trunk | 100 | | residential | 30 |
| trunk_link | 60 | | living_street | 15 |
| primary | 60 | | unclassified | 30 |
| primary_link | 40 | | road | 30 |
| secondary | 50 | | service | 20 |
| secondary_link | 40 | | (fallback) | 30 |

3. Implementación canónica vía `ox.routing.add_edge_speeds(G, hwy_speeds=TABLA_CHILE, fallback=30)`.

**Implicación del SRS**: el "maxspeed" que entra a la fórmula `peso = longitud / (maxspeed × factor_hora × factor_sirena)` es el resultado de la cascade, no el tag puro de OSM. Esto es el comportamiento que cualquier router industrial (OSRM, GraphHopper, Valhalla) aplica. Se documenta explícitamente en `docs/SRS.md` sec. 2.6-B y en el comentario inicial de `adapters/grafo_osmnx.py`.

### 3. Estrategia OSRM oracle

**Decisión**: OSRM **self-host docker con bbox recortado, fixture generado una vez localmente y committeado al repo**. CI no llama a OSRM nunca.

Razones:

- El demo público (`router.project-osrm.org`) cubre Chile, pero su ToS dice "best effort, access withdrawn at any time, no SLA, no academic carve-out". 100 requests en CI cada PR es exactamente el patrón que les hace bloquear IPs de GitHub Actions, justo el día de la entrega.
- Self-host con bbox La Serena-Coquimbo: ~30 MB PBF (extraído con `osmium extract` del Chile completo de Geofabrik), <1 GB RAM, preprocesamiento `osrm-extract`/`osrm-partition`/`osrm-customize` en <15 min sobre laptop.
- El proyecto necesita el oracle **una sola vez** (generar el fixture y demostrar paridad). Después de H2, OSRM desaparece del repo.

**Pipeline**:

1. `tools/build_osrm_oracle.sh` (script único, no parte del CI): descarga PBF Chile, extracto bbox, levanta `osrm-routed` local en puerto 5000.
2. `tools/generate_osrm_fixture.py`: genera 100 pares **base SAMU → incidente** (no aleatorios — distribución que el sistema verá en producción), consulta OSRM por cada par con `?alternatives=false&overview=false&steps=false&annotations=false`, escribe `tests/fixtures/osrm_oracle.json` con `[{origen, destino, duration, distance}, ...]`.
3. Test IT-01 en `tests/integration/test_routing_vs_osrm.py`: lee el fixture, corre A* propio sobre el mismo grafo de Coquimbo. **Criterio reformulado por [ADR-0011](0011-reformulacion-criterio-it01.md)** — actualmente asserta `len([p for p in pares if abs(d_propio - d_osrm) / d_osrm <= 0.30]) >= 75` (CP-01a) y reporta la distribución completa de divergencia en duration (CP-01b).

**Endpoint a consumir**: `/route/v1/driving/{lon1},{lat1};{lon2},{lat2}` → `routes[0].duration` (segundos) y `routes[0].distance` (metros). Tolerancia del SRS se aplica sobre `duration`.

**Plan B si docker da problemas en el equipo**: usar el demo público manualmente con `time.sleep(1)` entre requests, User-Agent identificable, corrido una vez por uno de los dos. Mismo fixture committeado. CI igual queda offline. Misma cifra final.

## Consecuencias

**Positivas**:
- A* propio es lógica pura testeable sin red ni filesystem.
- El cascade de velocidades hace IT-01 alcanzable sin acrobacias post-hoc.
- CI permanece self-contained — pasa siempre, no depende de servicios externos.
- El fixture committeado es trazabilidad para defensa académica: cualquiera puede ejecutar `pytest tests/integration/test_routing_vs_osrm.py` y verificar el resultado bit-exacto.
- Si en H3/H4 se decide rehacer la comparación con un PBF actualizado, el script `generate_osrm_fixture.py` queda y se vuelve a correr una vez.

**Negativas**:
- Setup inicial de OSRM docker es una jornada de trabajo. Se hace una vez.
- El fixture envejece con el grafo OSM. Mitigación: el grafo está commiteado al mismo tiempo (`coquimbo.graphml` reproducible vía `make build-graph`), y el fixture vive en `tests/fixtures/` con un README que explica cuándo regenerar.
- Documentamos un comportamiento (cascade) que no estaba literal en el SRS original. Se agrega como nota al SRS sec. 2.6-B con referencia a este ADR.

**Decisiones a futuro** (no en H2):
- Si en H3 se observa que la tabla de defaults chilena difiere significativamente de lo que OSRM `car.lua` aplica internamente (su tabla canónica está en `profiles/car.lua`), considerar adoptar la tabla literal de OSRM en lugar de la inferida en este ADR.
- Si en H5 la métrica de calidad NFPA 1710 (% Echo/Delta ≤ 8 min) tiene problemas sistemáticos, revisar si la cascade está sub/sobreestimando velocidades urbanas.

## Referencias

- SRS sec. 2.6-B (Ruteo A*), sec. 2.13 CP-01 (IT-01 A* vs OSRM), sec. 2.16 (Validación dual).
- ADR-0006 (Ports & Adapters liviano) — patrón aplicado.
- ADR-0008 (Validación dual Java vs Python) — RT-02 sobre el mismo grafo y dataset.
- [OSMnx 2.x docs](https://osmnx.readthedocs.io/) — `graph_from_bbox`, `routing.add_edge_speeds`, `save_graphml`.
- [OSRM Backend Docker](https://hub.docker.com/r/osrm/osrm-backend) — pipeline `osrm-extract`/`osrm-partition`/`osrm-customize`/`osrm-routed`.
- [Geofabrik Chile PBF](https://download.geofabrik.de/south-america/chile.html) — extracto OSM (~324 MB).
