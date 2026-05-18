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
| **RF-01** Validación de coordenadas IV Región en tiempo real | `interfaces/api` + `interfaces/cli` | _Validador de rango (pendiente)_ — ver [SRS sec. 2.7 RN-01](../SRS.md#27-reglas-de-negocio) | [CP-09](../SRS.md#213-casos-de-prueba) | Coordenadas fuera de `lat ∈ [−30.5, −29.5] ∧ lon ∈ [−71.7, −70.5]` rechazadas antes de A*; sin log de despacho generado | 🟡 H1 |
| **RF-02** Árbol de triaje MPDS-subset (Alpha..Echo) | `domain/triaje/` → [`arbol.py`](../../core-python/src/sentinel_dispatch/domain/triaje/arbol.py), [`tipos.py`](../../core-python/src/sentinel_dispatch/domain/triaje/tipos.py) | `clasificar_mpds(respuesta)` aplica las 9 reglas del SRS sec. 2.6-A en orden estricto | `test_regla_1_*` .. `test_regla_9_*` (9 tests) + `test_clasificacion_dataset[I-01..I-12]` (12 tests) | Cada respuesta válida produce la categoría MPDS esperada por la regla disparada; 12/12 incidentes del dataset clasificados correctamente | ✅ |
| **RF-03** Grafo OSM + ruteo A* con pesos calibrados | `domain/routing/` + `adapters/grafo_osmnx.py` | `a_estrella(grafo, origen, destino, factor_hora, factor_sirena)` (pendiente) | [CP-01](../SRS.md#213-casos-de-prueba) (A* vs OSRM ±5%) · CP-02 (factor_hora) · CP-03 (factor_sirena) | ETA dentro de tolerancia ±5% frente al oracle OSRM en 95% de 100 rutas; relación de ETAs consistente con factor de tráfico | 🟡 H2 |
| **RF-04** Función de costo multiobjetivo `α·T_viaje + β·Penalización_Idoneidad` | `domain/dispatch/` → `funcion_costo.py` | `costo(unidad, incidente, factores=...)` (pendiente) | [CP-04](../SRS.md#213-casos-de-prueba) Charlie+Básica · [CP-05](../SRS.md#213-casos-de-prueba) Echo+Básica | β = 600 s convierte la jerarquía MPDS×Tipo en penalización aditiva; Echo + Básica retorna `+∞` (excluida del argmin) | 🟡 H3 |
| **RF-05** Selección óptima por `argmin_u Costo(u, i)` | `domain/dispatch/` → `seleccion.py` | `seleccionar_unidad(unidades_disponibles, incidente)` (pendiente) | CP-04 · CP-11 (empate lexicográfico) | Unidad seleccionada minimiza el costo; ante empate se desempata por ID lexicográfico ascendente | 🟡 H3 |
| **RF-06** Log inmutable JSON de cada despacho confirmado | `adapters/log_jsonl.py` | `append_evento(log, evento)` sobre JSONL append-only (ADR-0007) | [CP-08](../SRS.md#213-casos-de-prueba) intento de edición | Edición rechazada con HTTP 403; entrada de auditoría generada; registro original sin cambios | 🟡 H4 |
| **RF-07** Visualización de la ruta A* en mapa | `interfaces/` (notebook Leaflet, F5 diferido) | _Notebook de visualización (pendiente, bonus)_ | Verificación visual durante FTR-01 | Ruta A* renderizada sobre tiles OSM con marcadores de incidente y unidad asignada | ⛔ post-H5 bonus |
| **RF-08** Re-despacho automático con confirmación humana | `domain/dispatch/` → `redespacho.py` | `evaluar_redespacho(unidad_actual, nuevo_incidente, flota)` (pendiente) | [CP-06](../SRS.md#213-casos-de-prueba) progreso 40% · [CP-07](../SRS.md#213-casos-de-prueba) progreso 60% | Propuesta presentada al operador solo si categoría nueva > actual ∧ progreso ≤ 50% ∧ existe cobertura alternativa | 🟡 H3 |
| **RF-09** Panel de unidades en tiempo real | `interfaces/api` + UI HTMX (F5 diferido) | _Endpoint `/unidades/estado` (pendiente)_ | Verificación funcional durante FTR-02 | Estado actualizado refleja transiciones Disponible↔EnRuta↔EnEscena↔Taller con coordenadas | ⛔ post-H5 (ADR-0004 deferred) |
| **RF-10** Detección de saturación y candidatas a re-dirección | `application/` → `saturacion.py` | `detectar_saturacion(flota)` (pendiente) | [CP-10](../SRS.md#213-casos-de-prueba) flota saturada | Sistema reporta saturación; lista candidatas EnRuta ordenadas por progreso ascendente | 🟡 H3 |
| **RF-11** Exportación de logs CSV/JSON | `adapters/exportador.py` | `exportar(logs, formato={csv,json})` (pendiente) | _Test funcional (pendiente, post-H4)_ | Logs exportados conservan campos del esquema y son legibles por herramientas estándar | 🟡 H4 |
| **RF-12** Modo simulación sobre flota ficticia | `application/` → `simulacion.py` | `simular(flota_ficticia, incidente)` (pendiente) | _Test funcional (pendiente)_ | Cálculo completo se ejecuta sin afectar el estado operativo real; resultado claramente marcado como simulación | 🟡 H4 |

## 3. Reglas de Negocio

| Regla | Módulo asociado | Función / invariante | Caso de prueba | Resultado esperado | Estado |
|---|---|---|---|---|---|
| **RN-01** Validación de rango IV Región | `interfaces/api` | `validar_coordenadas(lat, lon)` (pendiente) | CP-09 | Rechazo con mensaje "Coordenadas fuera del área de cobertura" antes de cualquier cálculo | 🟡 H1 |
| **RN-02** Saturación crítica → flag `despacho_suboptimo` (no bloqueo) | `domain/dispatch/` | `marcar_suboptimo(unidad, incidente)` (pendiente) | CP-05 | Echo/Delta con única Básica disponible: despacho ejecutado con `despacho_suboptimo: true` en el log | 🟡 H3 |
| **RN-03** Log inmutable | `adapters/log_jsonl.py` | Append-only JSONL (ADR-0007) | CP-08 | Edición rechazada; entrada de auditoría adicional generada | 🟡 H4 |
| **RN-04** Unidades en Taller excluidas | `application/` | `filtrar_disponibles(flota)` (pendiente) | _Test (pendiente)_ | Unidades en `Taller` no aparecen en el `argmin` bajo ninguna circunstancia | 🟡 H3 |
| **RN-05** Rendimiento ≤ 1 s para 50 unidades | Pipeline completo (`application/`) | Métrica end-to-end | CP-12 | `triaje + A*×50 + argmin ≤ 1000 ms` en el servidor de prueba | 🟡 H4 |
| **RN-06** Confirmación humana de re-despacho | `domain/dispatch/redespacho.py` | `evaluar_redespacho()` solo emite propuesta | CP-06 | Re-despacho propuesto, nunca ejecutado sin confirmación del operador | 🟡 H3 |
| **RN-07** Append-only de logs | `adapters/log_jsonl.py` | Identico a RN-03 (separa concepto: "no modificar" vs "solo agregar") | CP-08 | Intento de modificar registro existente falla con error y alerta de auditoría | 🟡 H4 |
| **RN-08** Saturación de flota | `application/saturacion.py` | `detectar_saturacion(flota)` (pendiente) | CP-10 | Sin Disponibles: reporta saturación + lista EnRuta ordenada por progreso | 🟡 H3 |
| **RN-09** Snap al nodo OSM si > 500 m | `adapters/grafo_osmnx.py` | `snap_a_nodo(grafo, coord, tolerancia_m=500)` (pendiente) | _Test (pendiente, post-H2)_ | Coordenadas válidas sin nodo cercano: snap al más cercano + alerta visual con distancia | 🟡 H2 |
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
| **RT-01** Núcleo de cálculo en Python y Java | `core-python/` + `core-java/` | Python: `domain/triaje/` ✅. Java: esqueleto Maven con `Main.java` + `SmokeTest.java` 🟡 | 🟡 H3-J |
| **RT-02** Resultados equivalentes dentro de tolerancia | `tools/compare_outputs.py` | Validador implementado; sin datos a comparar hasta que el core Java sea funcional | 🟡 post-H3-J |
| **RT-03** Documentar diferencias detectadas | SRS sec. 2.16 ("Diferencias previsibles") + reporte automático | Diferencias previsibles documentadas; reporte automático pendiente | 🟡 H4 |
| **RT-04** Justificar implementación más adecuada | Informe final (H5) | Tabla comparativa preparada en SRS sec. 2.16 ("Justificación de adecuación") | 🟡 H5 |

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

### 5.2 Módulos pendientes — `routing/`, `dispatch/`, `application/`, `adapters/`

Estos módulos están **diseñados** (SRS + ADR + vista C4) pero su implementación corresponde a hitos posteriores del cronograma (H2/H3/H4). Para la Segunda Evaluación se documentan en esta matriz como `🟡 pendiente` con la función planificada y el caso de prueba del SRS al que responderán. La defensa argumentará: el diseño está cerrado, la implementación se ejecuta secuencialmente para evitar duplicar bugs entre Python y Java (ver [README §Anti-patrones](../../README.md#anti-patrones-detectados)).

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
