# Matriz de Trazabilidad — Sentinel-Dispatch

> Mapeo **Requisito → Diseño → Código → Prueba → Resultado esperado** para la Segunda Evaluación del 2026-05-25 (GCS, UCEN).
>
> Fuente normativa: [SRS Sentinel-Dispatch](../SRS.md). Patrón arquitectónico: Ports & Adapters liviano (ver [ADR-0006](../architecture/decisions/0006-ports-and-adapters.md)). Estado del repositorio reflejado al `HEAD` de `main` al momento de redacción.

## 1. Alcance y leyenda

La matriz cubre los **doce Requisitos Funcionales** (RF-01..RF-12), las **diez Reglas de Negocio** (RN-01..RN-10) y los **cuatro Requisitos Transversales** (RT-01..RT-04) del SRS. Cada fila los conecta con su módulo del repositorio, la función concreta que lo implementa (o el placeholder, si aún no está implementado), el o los casos de prueba que lo verifican y el resultado esperado.

| Símbolo | Significado |
|---|---|
| ✅ | Implementado y verificado con tests verdes |
| 🟡 | Diseñado en SRS + ADR pero no implementado todavía (hito futuro) |
| ⛔ | Fuera de v1 (documentado en SRS sec. 2.14 R-03 o ADR `deferred`) |

**Hitos del roadmap (ver [README del proyecto](../../README.md))** — H1: triaje funcional 31-may · H2: routing A* 14-jun · H3: dispatch + re-despacho 28-jun · H3-J: núcleo Java 05-jul · H4: dataset completo + dual 10-jul · H5: informe final 15-jul.

**Tipología de pruebas (pauta Segunda Evaluación):**

| Tipo | Definición operativa en este proyecto |
|---|---|
| Normal | Entrada válida del dominio que dispara el camino feliz de la regla o el cálculo. |
| Borde | Entrada en la frontera entre dos resultados (orden de reglas, igualdad, próximo al umbral). |
| Error | Entrada inválida o intento de violar invariantes; debe lanzar excepción o rechazo controlado. |
| Regla de Negocio | Verifica una invariante o restricción del dominio declarada en SRS sec. 2.7 o equivalente. |

## 2. Matriz principal — Requisitos Funcionales

| Requisito | Módulo asociado | Función implementada | Caso de prueba | Resultado esperado | Estado |
|---|---|---|---|---|---|
| **RF-01** Validación de coordenadas IV Región en tiempo real | `domain/incidente/` + `interfaces/api` | `validar_coordenadas_iv_region(lat, lon)` ([validacion.py](../../core-python/src/sentinel_dispatch/domain/incidente/validacion.py)) expuesta vía `POST /v1/incidentes/validar-coordenadas` ([main.py](../../core-python/src/sentinel_dispatch/interfaces/api/main.py)); adapter `OsmnxGrafoVial.nodo_mas_cercano` delega como segunda barrera (ADR-0012) | [CP-09](../SRS.md#213-casos-de-prueba) | Coordenadas fuera de `lat ∈ [−30.5, −29.5] ∧ lon ∈ [−71.7, −70.5]` rechazadas con HTTP 422 antes de A*; sin log de despacho generado | ✅ (vía [test_validacion_coordenadas.py](../../core-python/tests/unit/domain/incidente/test_validacion_coordenadas.py) + [test_api_validacion_coordenadas.py](../../core-python/tests/integration/test_api_validacion_coordenadas.py)) |
| **RF-02** Árbol de triaje MPDS-subset (Alpha..Echo) | `domain/triaje/` → [`arbol.py`](../../core-python/src/sentinel_dispatch/domain/triaje/arbol.py), [`tipos.py`](../../core-python/src/sentinel_dispatch/domain/triaje/tipos.py) | `clasificar_mpds(respuesta)` aplica las 9 reglas del SRS sec. 2.6-A en orden estricto | `test_regla_1_*` .. `test_regla_9_*` (9 tests) + `test_clasificacion_dataset[I-01..I-12]` (12 tests) | Cada respuesta válida produce la categoría MPDS esperada por la regla disparada; 12/12 incidentes del dataset clasificados correctamente | ✅ |
| **RF-03** Grafo OSM + ruteo A* con pesos calibrados | `domain/routing/` + `adapters/grafo_osmnx.py` | `a_estrella(grafo, origen, destino, factor_hora, factor_sirena)` ([a_estrella.py](../../core-python/src/sentinel_dispatch/domain/routing/a_estrella.py)) | [CP-01a](../SRS.md#213-casos-de-prueba) (paridad de distancia A* vs OSRM ±30%, ADR-0011) · CP-02 (factor_hora) · CP-03 (factor_sirena) | A* propio recorre rutas con `\|Δ_distance\|/d_OSRM ≤ 0.30` en ≥ 75/100 pares del fixture OSRM (v2: 78/100). **CP-01a-95 cumplido** sobre fixture v3 (N=300, cartesiano): fracción dentro de ±30 % = 0.897, IC95 inferior 0.860 ≥ 0.75, P(≥0.75)=100 % ([ADR-0016](../architecture/decisions/0016-camino-95-cp01a.md) §Resultado, eval-95 2026-06-02); divergencia en duration reportada vía log | ✅ H2 (CP-01a/b) + ✅ H5 (CP-01a-95) vía [test_routing_vs_osrm.py](../../core-python/tests/integration/test_routing_vs_osrm.py) (`test_cp01a_95_fixture_v3`) |
| **RF-04** Función de costo multiobjetivo `α·T_viaje + β·Penalización_Idoneidad` | `domain/dispatch/` → [`funcion_costo.py`](../../core-python/src/sentinel_dispatch/domain/dispatch/funcion_costo.py) | `costo(unidad, incidente, t_viaje_s) → CostoDespacho` con `α=1.0`, `β=600s` y `TABLA_PENALIZACION_IDONEIDAD` exhaustiva (10 entradas); decisión arquitectónica en [ADR-0014](../architecture/decisions/0014-funcion-costo-dispatch.md) | [CP-04](../SRS.md#213-casos-de-prueba) Charlie+Básica · [CP-05](../SRS.md#213-casos-de-prueba) Echo+Básica | Echo/Delta + Básica → `math.inf`; Charlie + Básica → `1.0` (=600s); Avanzada lejana gana a Básica cercana en Charlie (CP-04); excepciones `UnidadInelegibleError` (RN-04, Taller) y `TViajeInvalidoError` (NaN/negativo) | ✅ H3 fase 1 (función de costo) — argmin pendiente |
| **RF-05** Selección óptima por `argmin_u Costo(u, i)` | `domain/dispatch/` → [`seleccion.py`](../../core-python/src/sentinel_dispatch/domain/dispatch/seleccion.py) | `seleccionar_unidad(unidades, incidente, tiempos_viaje)` → `ResultadoSeleccion` con `elegida`, `costo_elegida`, `candidatos` ordenados por `(costo, id)` (desempate CP-11) | CP-04 · CP-11 (empate lexicográfico) | Unidad seleccionada minimiza el costo; empate finito se desempata por `unidad.id` lex asc; Taller excluido silenciosamente; ``elegida=None`` si todas son inf (saturación de idoneidad, manejada por application) | ✅ H3 fase 2 |
| **RF-06** Log inmutable JSON de cada despacho confirmado | `adapters/repositorio_jsonl.py` + `ports/repositorio_eventos.py` ([ADR-0018](../architecture/decisions/0018-schema-evento-log.md)) | `JsonlRepositorioEventos.append(EventoLog)` sobre JSONL append-only (ADR-0007). Activable desde `sentinel run-dataset --log-eventos PATH`. Payload bit-exacto con schema RT-02 vía `serializar_resultado_despacho` | [CP-08](../SRS.md#213-casos-de-prueba) intento de edición (spike) | Spike CP-08 (`test_repositorio_jsonl_append_only.py::TestSpikeCP08`): edición externa detectable via `ValidationError`/`EventoDuplicadoError` al reabrir; el adapter no expone API de update/delete (RN-03/RN-07 estructural) | ✅ |
| **RF-07** Visualización de la ruta A* en mapa | `interfaces/` (notebook Leaflet, F5 diferido) | _Notebook de visualización (pendiente, bonus)_ | Verificación visual durante FTR-01 | Ruta A* renderizada sobre tiles OSM con marcadores de incidente y unidad asignada | ⛔ post-H5 bonus |
| **RF-08** Re-despacho automático con confirmación humana | `domain/dispatch/` → [`redespacho.py`](../../core-python/src/sentinel_dispatch/domain/dispatch/redespacho.py) | `evaluar_redespacho(unidad_actual, incidente_actual, incidente_nuevo, progreso_pct, flota, tiempos_viaje)` → `PropuestaRedespacho(procede, razon, unidad_de_reemplazo, ...)` | [CP-06](../SRS.md#213-casos-de-prueba) progreso 40% · [CP-07](../SRS.md#213-casos-de-prueba) progreso 60% | Tres condiciones RN-06 evaluadas en orden: criticidad creciente → progreso ≤ 50% → cobertura alternativa. Veredicto humanlegible en `razon`. Nunca ejecuta — solo propone | ✅ H3 fase 2 |
| **RF-09** Panel de unidades en tiempo real | `interfaces/api` + UI HTMX (F5 diferido) | _Endpoint `/unidades/estado` (pendiente)_ | Verificación funcional durante FTR-02 | Estado actualizado refleja transiciones Disponible↔EnRuta↔EnEscena↔Taller con coordenadas | ⛔ post-H5 (ADR-0004 deferred) |
| **RF-10** Detección de saturación y candidatas a re-dirección | `application/` → [`saturacion.py`](../../core-python/src/sentinel_dispatch/application/saturacion.py) | `detectar_saturacion(flota, progreso_por_unidad)` → `EstadoSaturacion(saturada, candidatas_redireccion)`; candidatas EnRuta ordenadas por `(progreso_pct asc, unidad.id lex asc)`; default conservador `progreso=0.0` para EnRuta sin progreso provisto | [CP-10](../SRS.md#213-casos-de-prueba) flota saturada | Sistema reporta saturación cuando ninguna unidad está en `DISPONIBLE`; lista candidatas EnRuta para re-dirección manual del operador | ✅ H3 fase 3 |
| **RF-11** Exportación de logs CSV/JSON | `adapters/exportador.py` + `interfaces/cli/export_cmd.py` | `exportar_a_csv(eventos, path)` y `exportar_a_json(eventos, path)`; CLI `sentinel export --formato {csv,json} --in EVENTOS.jsonl --out PATH`. CSV con flatten de `payload_*` y encoding `utf-8-sig` (BOM Excel); JSON como array indentado sin BOM | `test_exportador.py` (14 UT — flatten, CSV/JSON Normal/Borde, end-to-end CLI con archivo inexistente o corrupto) | Logs derivados con union de columnas para payloads heterogéneos; el log canónico JSONL no se modifica (RN-03 preservado, este subcomando solo lee) | ✅ |
| **RF-12** Modo simulación sobre flota ficticia | `application/simulacion.py` + `interfaces/cli/simular_cmd.py` | `simular(incidentes, flota_ficticia, grafo, *, repositorio_eventos=None) → ReporteSimulacion`. **Semántica v1**: SIN evolución temporal entre incidentes (cada uno ve la flota inicial). Determinístico — equivalente a paralelizar conceptualmente. Para event-driven con liberación por `eta_segundos` haría falta reloj virtual + ADR nuevo. Persistencia **opt-in** vía `repositorio_eventos` para no contaminar el log operativo. CLI: `sentinel simular --flota --incidentes --graph --out [--persistir-en]` | `test_simulacion.py` (7 UT — Normal/Borde/RN/Métricas: resultados+métricas correctas, sin evolución temporal, lista vacía, flota vacía=100% saturación, default no escribe a repo, con repo escribe N eventos con prefijo `SD-SIM-`, pcts suman 100) | Reporte agregado: lista de `ResultadoDespacho` + pct por motivo + ETA media/p95. El reporte JSON queda etiquetado `"modo": "simulacion"` para distinguir del modo operativo | ✅ |
| **CP-01c'** Paridad post-calibración duration ±30 % en ≥ 75/100 | `adapters/grafo_osmnx.py:cargar_grafo_iv_region(factor_calibracion=0.80)` + `domain/routing/a_estrella_snap_edge.py` (A* con snap-to-edge sobre `a_estrella_calibrado`) + `domain/routing/geometria.py:proyectar_en_polilinea` | Medición en `test_routing_vs_osrm.py::test_cp01c_snap_to_edge` | Snap-to-edge (H5-cal-3, 2026-05-28): **78/100 dentro de ±30 %** (mediana 0.170) a `factor_calibracion=0.80`. El objetivo histórico ±15 %/≥85 (ADR-0013) NO se alcanzó (máx 52/100 a factor 0.75): brecha residual estructural vs el modelo `car.lua` de OSRM. Criterio recalibrado a ±30 %/≥75 —mismo umbral que CP-01a usa para `distance`— en [ADR-0021](../architecture/decisions/0021-cp01c-snap-to-edge-criterio-realista.md); ADR-0013 promovido a `accepted`. Test pasa (ya no es `xfail`). | ✅ H5 (snap-to-edge, criterio recalibrado CP-01c' por ADR-0021) |

## 3. Reglas de Negocio

| Regla | Módulo asociado | Función / invariante | Caso de prueba | Resultado esperado | Estado |
|---|---|---|---|---|---|
| **RN-01** Validación de rango IV Región | `domain/incidente/validacion.py` | `validar_coordenadas_iv_region(lat, lon)` lanza `CoordenadasFueraDeRangoError` (ValueError) con mensaje normativo `MENSAJE_FUERA_DE_RANGO` (ADR-0012) | CP-09 | Rechazo con mensaje "Coordenadas fuera del área de cobertura (IV Región)." antes de cualquier cálculo | ✅ |
| **RN-02** Saturación crítica → flag `despacho_suboptimo` (no bloqueo) | `application/despachar_ambulancia.py::_fallback_rn02_basica` | Fallback explícito en orquestador: si única Disponible es Básica para Echo/Delta, elige Básica de menor `T_viaje` y marca `despacho_suboptimo=True` + `motivo=SUBOPTIMO_RN02`. Decisión documentada en [ADR-0015](../architecture/decisions/0015-fallback-rn02-suboptimo.md) | CP-05 (con fallback) | Echo/Delta + única Básica: despacho ejecutado, `costo_elegida.es_infinito=True` pero `t_viaje_s` preservado para auditoría; warning emitido a logging | ✅ H3 fase 3 |
| **RN-03** Log inmutable | `ports/repositorio_eventos.py` (Protocol sin `update`/`delete`) + `adapters/repositorio_jsonl.py` (append-only JSONL, ADR-0007/ADR-0018) | CP-08 | Tests estructurales (`test_repositorio_jsonl.py::TestReglasNegocio`) verifican que ni el Protocol ni el adapter exponen métodos de mutación; intento de re-escritura levanta `EventoDuplicadoError`. | ✅ |
| **RN-04** Unidades en Taller excluidas | `domain/dispatch/funcion_costo.py` + `application/` | `costo()` lanza `UnidadInelegibleError` si `unidad.estado is EstadoUnidad.TALLER`; el filtrado preventivo en application/ llega en PR siguiente | _RN cubierta en `test_funcion_costo.py::TestCostoError::test_unidad_taller_lanza`_ | Unidad en `Taller` no entra al cálculo bajo ninguna circunstancia; defensa ruidosa si el caller no filtra | ✅ H3 fase 1 (excepción de dominio) |
| **RN-05** Rendimiento ≤ 1 s para 50 unidades | Pipeline completo (`application/`) | Métrica end-to-end | CP-12 — spike en `tools/spike_cp12_performance.py`; test integration con marker `slow` en `test_performance_50_unidades.py` | **Criterio ajustado por evidencia empírica ([ADR-0019](../architecture/decisions/0019-spike-cp12-criterio-ajustado.md))**: `p95 ≤ 2000 ms` (medido: 1941 ms con A* secuencial). El criterio SRS original (≤ 1000 ms) no se cumple con la implementación actual; paralelización del A* queda como deuda v2. Cumplimiento del criterio ajustado verificado por test slow. | ✅ (criterio ajustado ADR-0019) |
| **RN-06** Confirmación humana de re-despacho | `domain/dispatch/redespacho.py` | `evaluar_redespacho()` emite `PropuestaRedespacho` con `procede` + `razon` + `unidad_de_reemplazo`. Constante `UMBRAL_PROGRESO_MAXIMO=0.50` | CP-06 / CP-07 | Re-despacho propuesto solo si las 3 condiciones se cumplen; cualquier veto retorna `procede=False` con razón humanlegible | ✅ H3 fase 2 |
| **RN-07** Append-only de logs | `adapters/repositorio_jsonl.py` (ADR-0018) | Idéntico a RN-03 (separa concepto: "no modificar" vs "solo agregar"). El adapter abre el archivo con modo `"a"` y crece monotónicamente | CP-08 | Test `test_dos_appends_consecutivos_solo_crecen_el_archivo` verifica que el tamaño del archivo es estrictamente creciente entre `append`s. | ✅ |
| **RN-08** Saturación de flota | `application/saturacion.py` | `detectar_saturacion(flota, progreso_por_unidad)` → `EstadoSaturacion(saturada, candidatas_redireccion)`; cobertura 100 %; cubierta por `test_saturacion.py` y por `test_despacho.py::test_cp10_saturacion_con_en_ruta_incluye_candidatas_ordenadas` | CP-10 | Sin Disponibles: reporta saturación + lista EnRuta ordenada por `(progreso_pct asc, unidad.id lex asc)` | ✅ H3 fase 3 |
| **RN-09** Snap al nodo OSM si > 500 m | `adapters/grafo_osmnx.py` | `OsmnxGrafoVial.nodo_mas_cercano()` + `distancia_snap_m()` ([grafo_osmnx.py](../../core-python/src/sentinel_dispatch/adapters/grafo_osmnx.py)) | 11 tests UT en [test_grafo_osmnx_snap.py](../../core-python/tests/unit/adapters/test_grafo_osmnx_snap.py) (Normal/Borde/Error/RN) | Coord exacta → snap idéntico (d=0); coord intermedia → nodo más cercano; coord lejana (>500 m) → `distancia_snap_m` supera el umbral RN-09 para que el borde dispare la alerta; coord fuera de rango lanza `NodoFueraDeRangoError` | ✅ H2 |
| **RN-10** Autenticación obligatoria + HTTPS | `interfaces/api` | Middleware FastAPI (pendiente) | _Test de seguridad (post-H4)_ | Toda operación requiere sesión autenticada; sin HTTPS rechaza la conexión | 🟡 H4 |

### Reglas de Negocio del módulo Triaje (ya verificadas)

Aunque las RN-01..RN-10 del SRS no nombran explícitamente el árbol, el dominio del triaje tiene **reglas de negocio propias** verificadas como tales:

| Invariante | Función | Caso de prueba | Resultado esperado |
|---|---|---|---|
| Orden estricto de criticidad Alpha < Bravo < Charlie < Delta < Echo (SRS sec. 2.6-A) | `CategoriaMPDS.__lt__` | `test_orden_estricto_alpha_a_echo`, `test_orden_es_transitivo` | Comparación consistente y transitiva entre las cinco categorías |
| Las 9 reglas se evalúan en orden estricto; ninguna se "salta" cuando una previa aplica | `clasificar_mpds()` | `test_inconsciencia_domina_sobre_sangrado_peligroso`, `test_sangrado_peligroso_domina_sobre_dolor_critico`, `test_dolor_critico_domina_sobre_dificultad_respiratoria`, `test_dificultad_respiratoria_domina_sobre_sangrado_activo` | Cuando múltiples condiciones aplican, gana la regla declarada antes |
| El dataset de aceptación cubre las 5 categorías MPDS | _Invariante del dataset_ | `test_dataset_cubre_las_cinco_categorias` | `{Alpha, Bravo, Charlie, Delta, Echo} ⊆ ground_truth` |
| El dataset mantiene los 12 incidentes declarados en SRS sec. 2.12 | _Invariante del dataset_ | `test_dataset_tiene_doce_incidentes` | `len(incidentes) == 12` |

## 4. Requisitos Transversales (validación dual Java vs Python)

| Requisito | Módulo asociado | Cobertura actual | Estado |
|---|---|---|---|
| **RT-01** Núcleo de cálculo en Python y Java | `core-python/` + `core-java/` | Python: `domain/{triaje,routing,dispatch}/` ✅. Java: núcleo funcional (triaje + A\* sobre JGraphT + función de costo + CLI espejo), **186 tests JUnit verdes** | ✅ |
| **RT-02** Resultados equivalentes dentro de tolerancia | [`tools/compare_outputs.py`](../../tools/compare_outputs.py) (job CI `compare`) | Ambos cores ejecutan el dataset y `compare_outputs.py` verifica la paridad: **12/12 OK · 0 WARN · 0 FAIL · bit-exacto** sobre rutas A\* y ETAs | ✅ |
| **RT-03** Documentar diferencias detectadas | [ADR-0017](../architecture/decisions/0017-contrato-jsonl-validacion-dual.md) + SRS sec. 2.16 + reporte automático | Asimetría de grafos documentada en ADR-0017 (Python `MultiDiGraph` vs Java deduplica por menor `longitudM`); reporte automático en [`rt-validation-report.md`](rt-validation-report.md) que emite el job `compare` | ✅ |
| **RT-04** Justificar implementación más adecuada | Informe final v1.0 (H5) | Tabla comparativa preparada en SRS sec. 2.16; la justificación formal se consolida en el **informe v1.0** | 🟡 H5 |

## 5. Cobertura de la pauta — pruebas por módulo

La pauta de la Segunda Evaluación pide, por módulo: **≥ 2 normales**, **≥ 2 de borde**, **≥ 2 de error** y **≥ 1 de regla de negocio**. Mapeo de los 36 tests verdes del módulo **triaje**:

### 5.1 Módulo `domain/triaje/` — ✅ cumple

| Tipo | Cantidad | Tests |
|---|---|---|
| **Normal** | 22 | 9 reglas (`test_regla_1_*` .. `test_regla_9_*`), 12 incidentes del dataset (`test_clasificacion_dataset[I-01..I-12]`), `test_nivel_sangrado_tiene_cuatro_niveles`, `test_nivel_dolor_toracico_tiene_tres_niveles`, `test_acepta_los_seis_campos_del_srs` |
| **Borde** | 5 | `test_no_es_estrictamente_menor_que_si_misma`, `test_inconsciencia_domina_sobre_sangrado_peligroso`, `test_sangrado_peligroso_domina_sobre_dolor_critico`, `test_dolor_critico_domina_sobre_dificultad_respiratoria`, `test_dificultad_respiratoria_domina_sobre_sangrado_activo` |
| **Error** | 3 | `test_nivel_sangrado_rechaza_valor_invalido`, `test_categoria_mpds_rechaza_valor_invalido`, `test_es_inmutable` (FrozenInstanceError) |
| **Regla de Negocio** | 4 | `test_orden_estricto_alpha_a_echo`, `test_orden_es_transitivo`, `test_dataset_cubre_las_cinco_categorias`, `test_dataset_tiene_doce_incidentes` |
| **Total** | **36** | ejecutados en **0.05 s** vía `uv run --project core-python pytest core-python/tests/unit/domain/triaje/` |

Mínimo solicitado por la pauta para el módulo: 7. Cobertura efectiva: 36 (5.1× el mínimo).

### 5.2 Módulo `domain/routing/` — ✅ cumple (H2)

Suite `core-python/tests/unit/domain/routing/` con **20 tests verdes** distribuidos entre A* puro y heurística Haversine:

| Tipo | Tests representativos |
|---|---|
| **Normal** | `test_camino_directo_es_optimo`, `test_camino_con_desvio_mas_corto_es_preferido`, `test_origen_igual_destino_retorna_cero_y_lista_unitaria`, `test_factor_sirena_14_reduce_eta`, `test_haversine_m_la_serena_coquimbo_aprox_11km`, `test_haversine_segundos_igual_a_distancia_sobre_vmax` |
| **Borde** | `test_tie_breaking_es_deterministico`, `test_haversine_m_mismo_punto_es_cero`, `test_haversine_segundos_valores_concretos[…]` (parametrizado, casos en frontera) |
| **Error** | `test_sin_camino_lanza_no_ruta_disponible_error`, `test_factor_hora_invalido_lanza_value_error[0.0|-1.0|-0.001]`, `test_factor_sirena_invalido_lanza_value_error[…]` |
| **Regla de Negocio** | `test_heuristica_admisible_h_origen_menor_que_eta_real` (admisibilidad ⇒ optimalidad), `test_haversine_m_es_simetrica`, `test_factor_hora_05_duplica_eta` (semántica de factores SRS sec. 2.6-B) |

### 5.3 Módulo `adapters/grafo_osmnx.py` — ✅ cumple (H2)

| Tipo | Cantidad | Tests |
|---|---|---|
| **Normal** | 3 | `test_coordenada_exacta_de_nodo_devuelve_ese_nodo`, `test_coordenada_intermedia_devuelve_el_nodo_mas_cercano`, `test_coordenada_cerca_de_tierras_blancas_devuelve_nodo_4` |
| **Borde** | 2 | `test_latitud_en_limite_inferior_no_lanza`, `test_longitud_en_limite_superior_no_lanza` |
| **Error** | 3 | `test_latitud_fuera_de_rango_inferior_lanza`, `test_longitud_fuera_de_rango_superior_lanza`, `test_grafo_sin_nodos_lanza` |
| **Regla de Negocio** | 3 | `test_distancia_snap_exacto_es_cero`, `test_distancia_snap_dentro_de_500m_es_aceptable_para_rn09`, `test_distancia_snap_mayor_a_500m_activa_alerta_rn09` |
| **Total** | **11** | suite `core-python/tests/unit/adapters/test_grafo_osmnx_snap.py` |

Validación IT-01 con OSRM oracle (CP-01a/b, ADR-0011): [test_routing_vs_osrm.py](../../core-python/tests/integration/test_routing_vs_osrm.py) — assert ≥ 75/100 pares con `|Δ_distance|/d_OSRM ≤ 0.30` (resultado v2: 78/100). Reporta también la distribución de divergencia en `duration`.

**CP-01a-95 cumplido (H5-eval-95, 2026-06-02, [ADR-0016](../architecture/decisions/0016-camino-95-cp01a.md) `accepted`)** — sobre el fixture v3 cartesiano (N=300, `osrm_oracle_v3.json`), el A* operativo alcanza fracción dentro de ±30 % = **0.897** con **IC95 inferior 0.860 ≥ 0.75** y **P(fracción ≥ 0.75) = 100 % ≥ 0.95** (bootstrap B=1000, semilla 2026; 13 pares irruteables por anclas oceánicas contados como miss). El margen estrecho de v2 era artefacto del sesgo a rutas cortas (ADR-0011 §V/L#3, ahora `resuelto`); con rutas largas inter-comuna la fidelidad de `distance` sube. Bootstrap en [bootstrap-cp01a-v3.md](bootstrap-cp01a-v3.md), outliers en [outliers-cp01a-v3.md](outliers-cp01a-v3.md), test `test_cp01a_95_fixture_v3` (`slow`).

**Blindaje defensa (2026-05-19)** — descomposición empírica de los 22 outliers vía [tools/analyze_outliers.py](../../tools/analyze_outliers.py): 55% `snap_endpoints` + 14% `snap_corto` (68% snap-to-node) + 14% `via_filtrada` (filtrado `car.lua`) + 18% `residual`. Tabla detallada en [outliers-cp01a.md](outliers-cp01a.md) y CSV en [outliers-cp01a.csv](outliers-cp01a.csv). Documentación del jitter (`radio=0.0013°`, distribución uniforme, seed=2026, generador `random.Random(seed).uniform`) ahora vive explícitamente en el header del fixture (v2). [ADR-0013](../architecture/decisions/0013-cp01c-criterio-calibrado.md) fijó *a priori* el criterio post-calibración esperable: **CP-01c — duration ±15% en ≥ 85/100** tras `factor_calibracion=0.85` + turn penalties. Medido en H5-cal-3 (2026-05-28), ese objetivo resultó inalcanzable (brecha estructural vs el modelo `car.lua` de OSRM); [ADR-0021](../architecture/decisions/0021-cp01c-snap-to-edge-criterio-realista.md) lo recalibró a **CP-01c' — duration ±30% en ≥ 75/100** (logrado 78/100 con snap-to-edge a `factor_calibracion=0.80`) y promovió ADR-0013 a `accepted`.

### 5.4 Módulo `domain/incidente/` — ✅ cumple (RF-01 / RN-01)

Suite `core-python/tests/unit/domain/incidente/test_validacion_coordenadas.py` con **13 tests verdes**, complementada por **7 tests** de integración del endpoint en `core-python/tests/integration/test_api_validacion_coordenadas.py` (CP-09 a nivel HTTP).

| Tipo | Cantidad | Tests representativos |
|---|---|---|
| **Normal** | 3 | `test_coquimbo_centro_no_lanza`, `test_la_serena_centro_no_lanza`, `test_ovalle_no_lanza` (rechazo intencional — Ovalle queda fuera del bbox normativo H1) |
| **Borde** | 4 | `test_latitud_en_limite_inferior_no_lanza`, `test_latitud_en_limite_superior_no_lanza`, `test_longitud_en_limite_inferior_no_lanza`, `test_longitud_en_limite_superior_no_lanza` |
| **Error** | 4 | `test_latitud_fuera_de_rango_inferior_lanza`, `test_longitud_fuera_de_rango_superior_lanza`, `test_nan_en_latitud_lanza`, `test_infinito_en_longitud_lanza` |
| **Regla de Negocio** | 2 | `test_cp09_textual_lat_minus_31_2_lon_minus_71_3` (CP-09 textual SRS sec. 2.13), `test_excepcion_es_subclase_de_value_error` |
| **Total UT** | **13** | suite `tests/unit/domain/incidente/` |
| **Integración HTTP** | 7 | `test_api_validacion_coordenadas.py` cubre CP-09 vía 422 con detalle estructurado + casos válidos + body malformado |

Decisión arquitectónica documentada en [ADR-0012](../architecture/decisions/0012-ubicacion-validador-coordenadas.md): el validador vive en dominio, el adapter `OsmnxGrafoVial` delega como segunda barrera, y `NodoFueraDeRangoError` pasa a ser subclase de `CoordenadasFueraDeRangoError` para preservar el contrato del adapter.

### 5.5 Módulo `domain/dispatch/` — ✅ fases 1+2 (H3 en curso)

Suite `core-python/tests/unit/domain/dispatch/` con **67 tests verdes** distribuidos en tres archivos: `test_funcion_costo.py` (38, PR #8), `test_seleccion.py` (15, PR #9) y `test_redespacho.py` (14, PR #9).

| Sub-módulo | Tipo | Cantidad | Tests representativos |
|---|---|---|---|
| `funcion_costo.py` | Normal/Borde/Error/RN | 38 | Tabla parametrizada (10 entradas) + CP-04 + CP-05 + Delta+Básica=∞ + Taller (RN-04) + determinismo |
| `seleccion.py` | Normal/Borde/Error/RN | 15 | `argmin` + CP-04 + CP-05 + CP-11 (desempate lex) + RN-04 (Taller excluido silencioso) + `hay_cobertura_alternativa` (3 casos) |
| `redespacho.py` | Normal/Borde/Error/RN | 14 | CP-06 (progreso 40% → procede) + CP-07 (progreso 60% → denegado) + las 3 condiciones RN-06 evaluadas en orden + borde 50% exacto |

Decisiones arquitectónicas: [ADR-0014](../architecture/decisions/0014-funcion-costo-dispatch.md) documenta la fórmula (`α=1.0`, `β=600s`), la tabla exhaustiva (10 entradas), la separación dominio/routing (T_viaje como input), y la separación dominio/fallback RN-02 (delegada a [ADR-0015] pendiente en PR #10).

### 5.6 Módulo `application/` — ✅ H3 fase 3 (cierra el hito)

Capa de orquestación que combina las piezas de dominio (`triaje`, `routing`, `dispatch`) en el caso de uso end-to-end. Cubre RF-10 (saturación), RN-02 (fallback `despacho_suboptimo`), RN-08 (detección de saturación) y el flujo completo del SRS sec. 2.5.

**Componentes:**

- [`application/despachar_ambulancia.py`](../../core-python/src/sentinel_dispatch/application/despachar_ambulancia.py) — `despachar(incidente, flota, grafo, factor_hora, factor_sirena, progreso_por_unidad)` orquesta snap + A* + selección + fallback + saturación. Retorna `ResultadoDespacho` con uno de cuatro `motivo`: `OPTIMO`, `PENALIZADO`, `SUBOPTIMO_RN02`, `SATURACION`. La política de fallback RN-02 vive en la función auxiliar `_fallback_rn02_basica`.
- [`application/saturacion.py`](../../core-python/src/sentinel_dispatch/application/saturacion.py) — `detectar_saturacion(flota, progreso_por_unidad)` reporta saturación de capacidad (RN-08) y lista candidatas EnRuta ordenadas por progreso ascendente (CP-10).
- [`application/tipos.py`](../../core-python/src/sentinel_dispatch/application/tipos.py) — value objects inmutables (`ResultadoDespacho`, `EstadoSaturacion`, `CandidataRedireccion`, `MotivoDespacho`).

Decisión arquitectónica documentada en [ADR-0015](../architecture/decisions/0015-fallback-rn02-suboptimo.md): la política RN-02 vive en application porque el dominio (`funcion_costo.py`) modela la idoneidad médica, no la política operativa de qué hacer cuando la idoneidad ideal no es alcanzable. Cuatro caminos posibles del orquestador resumidos en la tabla del ADR.

### 5.7 Módulos pendientes — H4 (exportador, simulación)

`adapters/repositorio_jsonl.py` (RF-06, RN-03, RN-07, CP-08) **ya implementado** en H4 fase 1 con ADR-0018 + 22 tests + spike CP-08 documentado. `adapters/exportador.py` (RF-11), `application/simulacion.py` (RF-12) y la calibración CP-01c (ADR-0013) llegan en las fases siguientes de H4.

## 6. Cómo regenerar / reproducir esta matriz

Cuando se agreguen nuevos módulos o pruebas, actualizar esta matriz junto con el commit que los introduzca. Comandos útiles para verificar el estado en local:

```bash
# Listar tests del módulo triaje con sus nombres exactos
uv run --project core-python pytest core-python/tests/unit/domain/triaje/ --collect-only -q

# Correr la suite y obtener la cuenta
uv run --project core-python pytest core-python/tests/unit/domain/triaje/ -v --no-cov

# Verificar que los IDs del dataset coinciden con la matriz
jq -r '.[] | .id' data/dataset/incidentes.json
```

## 7. Referencias cruzadas

- [SRS Sentinel-Dispatch](../SRS.md) — fuente normativa de RF, RN, RT, CP y riesgos.
- [Vista arquitectónica C4](../architecture/c4.md) — relación entre módulos y flujos.
- [ADR-0006 — Ports & Adapters liviano](../architecture/decisions/0006-ports-and-adapters.md) — patrón arquitectónico aplicado.
- [ADR-0008 — Validación dual Java vs Python](../architecture/decisions/0008-validacion-dual-java-python.md) — base de RT-01..RT-04.
- [ADR-0009 — Refinamiento del árbol MPDS-subset](../architecture/decisions/0009-refinamiento-arbol-triaje.md) — fundamento del módulo triaje.
- [README del proyecto](../../README.md) — roadmap y estado.
