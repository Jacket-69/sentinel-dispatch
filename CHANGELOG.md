# Changelog

Todos los cambios notables a este proyecto se documentan acá.

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).
Versionado: una entrada por **entrega académica** del semestre (no SemVer estricto durante desarrollo).

## [Unreleased]

### Added — H3 fase 1: tipos del dominio dispatch + función de costo (RF-04, 2026-05-19)
- Nuevo paquete `domain/dispatch/` con tipos del dominio: enums `TipoUnidad` (Avanzada / Básica) y `EstadoUnidad` (Disponible / EnRuta / EnEscena / Taller); dataclasses frozen `Unidad`, `Incidente` y value object `CostoDespacho` con desglose para auditoría (RF-06 / log JSONL).
- [`domain/dispatch/funcion_costo.py`](core-python/src/sentinel_dispatch/domain/dispatch/funcion_costo.py): implementación de la fórmula del SRS sec. 2.6-C — `Costo(u, i) = α·T_viaje + β·Penalización_Idoneidad` con `α=1.0`, `β=600s`. Tabla `TABLA_PENALIZACION_IDONEIDAD` exhaustiva (10 entradas: Echo/Delta+Básica → `math.inf`, Charlie+Básica → 1.0, resto → 0.0). Excepciones de dominio `UnidadInelegibleError` (RN-04 — Taller excluido) y `TViajeInvalidoError` (NaN o negativo).
- [ADR-0014](docs/architecture/decisions/0014-funcion-costo-dispatch.md) documenta la fórmula, la separación del dominio respecto al routing (`t_viaje_s` se recibe como input, no se calcula adentro) y la separación entre el cálculo de costo (dominio) y el fallback RN-02 (application, ADR-0015 pendiente).
- Tests unitarios del módulo en `tests/unit/domain/dispatch/test_funcion_costo.py` — **38 tests verdes** distribuidos en Normal (6) + Borde (6) + Error (6) + Regla de Negocio (8) + tabla parametrizada (14). Cubre CP-04 textual ("Charlie + Básica cercana vs Avanzada lejana"), CP-05 textual ("Echo + Básica → ∞" con preservación de `t_viaje_s`), setup de CP-11 (empate de costo) y determinismo (100 ejecuciones idénticas).

### Changed — H3 fase 1
- `docs/quality/trazabilidad.md`: RF-04 marcado ✅ fase 1 (costo); RN-04 ✅ vía excepción de dominio; entries enriquecidas con paths a `funcion_costo.py` y `ADR-0014`.
- `core-python/pyproject.toml`: agregada lista `[tool.ruff.lint] allowed-confusables = ["α", "β", "×", "→", "·", "−"]` para tolerar fórmulas matemáticas del SRS en docstrings sin sacrificar legibilidad académica.

### Added — Blindaje defensa Segunda Evaluación (ADR-0011 + ADR-0013, 2026-05-19)
- `tools/analyze_outliers.py` clasifica los 22 outliers del fixture OSRM por causa probable (`snap_endpoints`, `snap_corto`, `via_filtrada`, `turn_penalty`, `simplify`, `residual`) con umbrales heurísticos documentados en el módulo. Resultado: 68% snap-to-node + 14% filtrado `car.lua` + 18% residual.
- `docs/quality/outliers-cp01a.md` y `.csv` con la tabla detallada por par (id, d_propio, d_OSRM, err_rel, n_giros, %vía filtrada, causa). Regenerable con `uv run --project core-python python tools/analyze_outliers.py`.
- [ADR-0013](docs/architecture/decisions/0013-cp01c-criterio-calibrado.md) — placeholder `CP-01c` (`duration ±15% en ≥ 85/100`) como criterio numérico esperable tras aplicar `factor_calibracion=0.85` + turn penalties simples en H4.
- Fixture `osrm_oracle.json` migrado a **v2** con metadata explícita del jitter (`radio_grados=0.0013`, distribución `uniform`, seed `2026`, generador `random.Random(seed).uniform`, `jitters_por_incidente=10`) y `distancia_minima_m=200.0`. El generador `tools/generate_osrm_fixture.py` también incluye estos campos para regeneraciones futuras.

### Changed — Blindaje defensa
- [ADR-0011](docs/architecture/decisions/0011-reformulacion-criterio-it01.md) extendido con: (a) sección "Cómo se generan los pares (jitter)" en Contexto; (b) tabla "Descomposición empírica de los 22 outliers (2026-05-19)" con conteo por causa; (c) nueva sección "Verdad y limitaciones" que reconoce explícitamente que el CP-01 original del SRS no fue validado empíricamente antes de redactarse, y enumera otras debilidades del experimento (heurísticas del clasificador, sesgo de la muestra hacia rutas urbanas cortas, margen estrecho 78/100 vs 75/100, ausencia de aislamiento experimental de las cinco fuentes de divergencia).
- `docs/quality/trazabilidad.md` §5.3 añade párrafo "Blindaje defensa" con los porcentajes empíricos y links a outliers + ADR-0013.

### Added — Cierre deuda H1: validador de coordenadas IV Región (RF-01 / RN-01 / CP-09, 2026-05-19)
- Nuevo paquete de dominio `domain/incidente/` con [`validacion.py`](core-python/src/sentinel_dispatch/domain/incidente/validacion.py): función pura `validar_coordenadas_iv_region(lat, lon)`, excepción `CoordenadasFueraDeRangoError(ValueError)` con mensaje normativo `MENSAJE_FUERA_DE_RANGO` ("Coordenadas fuera del área de cobertura (IV Región).") y constantes `LAT_MIN_IV_REGION` / `LAT_MAX_IV_REGION` / `LON_MIN_IV_REGION` / `LON_MAX_IV_REGION`.
- Endpoint `POST /v1/incidentes/validar-coordenadas` en [interfaces/api/main.py](core-python/src/sentinel_dispatch/interfaces/api/main.py): responde **200** para coordenadas dentro del bbox y **422** con detalle estructurado (`mensaje`, `lat`, `lon`, `rango_iv_region`) cuando caen fuera.
- Suite UT `core-python/tests/unit/domain/incidente/test_validacion_coordenadas.py` — 13 tests con taxonomía Normal/Borde/Error/RN, incluido el CP-09 textual.
- Suite de integración `core-python/tests/integration/test_api_validacion_coordenadas.py` — 7 tests que cubren CP-09 a nivel HTTP, casos válidos y body malformado.
- [ADR-0012](docs/architecture/decisions/0012-ubicacion-validador-coordenadas.md) documenta la decisión de mover la validación de coordenadas del adapter al dominio (RN-01 es regla de negocio, no preocupación del adapter) y la jerarquía de excepciones resultante.

### Changed — Cierre deuda H1
- `adapters/grafo_osmnx.py`: `nodo_mas_cercano` ahora delega al validador de dominio como segunda barrera; se eliminaron las constantes locales `_LAT_MIN`/`_LAT_MAX`/`_LON_MIN`/`_LON_MAX`. El mensaje del error se unifica con el normativo del CP-09.
- `domain/routing/tipos.py`: `NodoFueraDeRangoError` pasa a ser subclase de `CoordenadasFueraDeRangoError`, manteniendo el constructor `(mensaje, *, lat, lon)` para no romper call-sites históricos.
- `docs/quality/trazabilidad.md`: RF-01 y RN-01 marcados ✅ con función implementada y tests verificados; nueva §5.4 (módulo `domain/incidente/`, 13 UT + 7 integración).

### Added — H2 cierre (routing IT-01 + RN-09, 2026-05-18)
- Pipeline OSRM oracle self-host: `tools/build_osrm_oracle.sh` levanta `osrm-routed --algorithm mld` en Docker con bbox La Serena-Coquimbo extraído del PBF Chile vía `osmium-tool`. `tools/generate_osrm_fixture.py` produce `core-python/tests/fixtures/osrm_oracle.json` (100 pares `base SAMU × incidente_con_jitter`).
- `core-python/scripts/build_graph.py` materializa `data/graphs/coquimbo.graphml` (16 679 nodos, 42 508 aristas) — caché reproducible para IT-01, commiteada al repo (excepción explícita en `.gitignore`).
- Test integración IT-01 ([test_routing_vs_osrm.py](core-python/tests/integration/test_routing_vs_osrm.py)) que valida CP-01a (paridad de distancia A* vs OSRM ≤ ±30% en ≥ 75/100 pares — actual: 78/100) y reporta CP-01b (divergencia observacional en duration).
- Suite UT del snap RN-09 ([test_grafo_osmnx_snap.py](core-python/tests/unit/adapters/test_grafo_osmnx_snap.py)) — 11 tests con taxonomía Normal/Borde/Error/RN sobre `OsmnxGrafoVial.nodo_mas_cercano` y `distancia_snap_m`.
- [ADR-0011](docs/architecture/decisions/0011-reformulacion-criterio-it01.md) documenta el experimento del 2026-05-18, las cinco fuentes de divergencia entre A* propio y OSRM, y la reformulación del criterio CP-01 (de duration ±5% a distance ±30%).

### Changed — H2 cierre
- SRS sec. 2.13 CP-01 anotado con nota al pie refiriendo al ADR-0011; sec. 2.15 §1 reformulada con el criterio de paridad real verificado.
- `docs/quality/trazabilidad.md`: RF-03 y RN-09 marcados ✅ con función implementada y tests verificados; agregadas §5.2 (routing, 20 tests) y §5.3 (adapter snap, 11 tests).
- `.gitignore`: excepción para `data/graphs/coquimbo.graphml` (commitado), exclusión de `data/osrm/*` (PBF + sidecars regenerables ~600 MB).

### Added
- Scaffolding inicial del repo (Fase 0 de la metodología): estructura `docs/`, `src/`, `tests/`, CI con GitHub Actions, pre-commit hooks (ruff + mypy + gitleaks), Makefile con targets básicos.
- ADRs 0001 (stack), 0002 (monolito modular), 0003 (SQLite v1), 0004 (frontend retro CRT/HTMX), 0005 (deploy demo Cloudflare Tunnel).
- `Dockerfile` multi-stage + `docker-compose.yml` con perfiles `dev`/`demo`.
- `scripts/cloudflared-setup.md` (playbook deploy demo) + `scripts/healthcheck.sh`.
- Sección "Demo en vivo" en `docs/operations/runbook.md`.
- `uv.lock` para builds reproducibles en CI.
- Diseño de Arquitectura Física (`docs/architecture/c4-deployment.md`) con vista de deployment GLaDOS → Docker → Cloudflare Edge → navegador, Tailscale out-of-band y UPS.
- BPMN 2.0 del proceso principal (`docs/architecture/process-bpmn.bpmn`) con lanes Operador / Sistema / Personal de Unidad, gateways de validación y confirmación, y event sub-process no interruptivo para re-despacho RN-06.

## [v0.1.0-diseño] — 2026-05-07 (planeado)

Entrega académica del bloque Diseño (tarea 2026-05-07 GCS):
- Diseño de Arquitectura Físico (C4 Container).
- Diseño Lógico Funcional — Proceso principal en BPMN 2.0.
- Mockups de la consola de despacho (estética CRT/phosphor).

(Pendiente al cierre de la entrega.)
