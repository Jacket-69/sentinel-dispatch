---
adr: 0008
title: Validación dual del núcleo de cálculo en Java y Python (RT-01..RT-04)
status: accepted
date: 2026-05-15
deciders: Benjamin López
tags: [adr, validacion, dual, java, python, rt]
---

# ADR 0008 — Validación dual del núcleo de cálculo en Java y Python

## Contexto

La plantilla oficial de SRS distribuida por el profesor Gonzalo Honores (archivo `Plantilla_Especificación_Requisitos.doc`, creada 2026-04-13) exige en su **Sección 3.2 — Requisito Transversal — Validación del núcleo de cálculo (Java vs Python)**:

> **RT-01**: El núcleo de cálculo deberá ser implementado o simulado en ambos lenguajes.
>
> **RT-02**: Los resultados deberán ser equivalentes dentro de un margen de tolerancia definido.
>
> **RT-03**: Se deberá documentar cualquier diferencia detectada.
>
> **RT-04**: Se deberá justificar cuál implementación es más adecuada.

Este requisito **transversal** se cayó en la normalización 30-abr → 6-may del SRS y vivió sin reflejo en la documentación durante 1 mes (descubierto el 2026-05-15 al revisar la plantilla original en `Inbox/` del vault). Restaurarlo y materializarlo es obligación académica.

Una versión anterior del SRS interno (docx del 30-abr) había escrito una sección 3.9 que reinterpretaba el RT como "OSRM (C++) como oracle externo basta para cumplir el espíritu". Esta interpretación **no cumple el texto literal del profe**, que pide explícitamente Java y Python. Se descarta.

## Decisión

Implementamos el **núcleo de cálculo** en Python como primario y en Java como **implementación dual mínima defendible**, aprovechando que la plantilla del profesor admite "implementado o simulado".

### Alcance del núcleo

"Núcleo de cálculo" se define operativamente como:

- **Triaje** — árbol MPDS-subset (lógica condicional pura).
- **Routing** — A* sobre grafo OSM cargado desde GraphML.
- **Dispatch** — función de costo `α·T + β·Pen`, argmin, tabla de penalización de idoneidad.

Lo que **no** se duplica en Java:

- Re-despacho (RF-08): flujo aplicativo, no núcleo de cálculo puro.
- Persistencia JSONL (ADR-0007).
- API REST.
- Generación del grafo OSM desde OSMnx: lo hace Python una vez (`core-python/scripts/build_graph.py`); Java consume el `.graphml` resultante.
- Validación de rango, autenticación, log de auditoría.

### Estructura monorepo

```
sentinel-dispatch/
├── core-python/              ← implementación primaria completa
├── core-java/                ← núcleo standalone (triaje + A* + costo + CLI)
├── data/
│   ├── graphs/coquimbo.graphml      ← generado por core-python, leído por ambos
│   └── dataset/incidentes.json      ← 12 incidentes compartidos
└── tools/
    └── compare_outputs.py    ← validador RT-02 con tolerancia
```

### Stack del core-java

| Capa | Tecnología |
|---|---|
| Lenguaje | Java 21 LTS (OpenJDK) |
| Build | Maven |
| Grafos + A* | JGraphT 1.5.x (importa GraphML nativo; `AStarShortestPath` con heurística custom) |
| JSON | Jackson |
| Tests | JUnit 5 + AssertJ |
| Cobertura | JaCoCo |
| Lint / format | Spotless + Checkstyle |

### Mecanismo de comparación (RT-02)

`tools/compare_outputs.py` ejecuta:

1. `cd core-python && python -m sentinel_dispatch run-dataset --out /tmp/python-out/`
2. `cd core-java && mvn exec:java -Dexec.args="run-dataset --out /tmp/java-out/"`
3. Compara JSON a JSON con tolerancias por campo:

| Campo | Tolerancia | Justificación |
|---|---|---|
| `categoria_mpds` | exact match | Categórica; no admite tolerancia |
| `unidad_seleccionada.id` | exact match | Determinista por desempate lexicográfico (CL-02) |
| `despacho_suboptimo` (bool) | exact match | Categórico |
| `eta_segundos` | ±5% | Diferencias por orden de relajación A* con empates |
| `costo.T_viaje` | ±5% | Idem |
| `costo.total` | ±5% | Idem |
| `ruta` (lista nodos) | mismo origen/destino, longitud ±10% | A* puede explorar caminos alternativos de costo equivalente |

4. Produce `docs/quality/rt-validation-report.md` con tabla por incidente, hallazgos clasificados (equivalencia OK / diferencia tolerable / diferencia significativa / discrepancia categórica) e hipótesis de causa.

### Hipótesis de diferencias esperadas (RT-03 anticipado)

- **Coma flotante**: Python `float` ≡ Java `double` (ambos IEEE 754 double precision), pero el orden de operaciones puede producir diferencias en bits menos significativos. Por eso `eta_segundos` se compara con tolerancia, no exact.
- **A* con empates**: misma heurística Haversine, mismo costo de arista, pero el orden de relajación de nodos con costos idénticos depende de la PriorityQueue interna (`heapq` Python vs `PriorityQueue` Java). Solución: desempate determinista por ID de nodo.
- **Carga de GraphML**: ambos cargan el mismo `coquimbo.graphml`; verificar al arrancar que el grafo cargado tiene el mismo conjunto de aristas (test de integridad inicial).

### Cumplimiento (mapeo RT → artefacto)

| RT | Artefacto que lo cumple |
|---|---|
| RT-01 | `core-python/` (completa) + `core-java/` (núcleo) |
| RT-02 | `tools/compare_outputs.py` ejecutado en CI; tolerancias documentadas en este ADR |
| RT-03 | `docs/quality/rt-validation-report.md` actualizado en cada push a `main` |
| RT-04 | `docs/quality/rt-justification.md` redactado al cierre del proyecto (~1-2 páginas) |

### Veredicto anticipado RT-04

Documento final compara Python vs Java sobre criterios concretos:

- **Ecosistema GIS**: Python gana fuerte (OSMnx no existe en Java).
- **Tipos**: Java gana en compile-time safety; Python con mypy strict se acerca.
- **Performance**: bench real sobre dataset + 50 unidades sintéticas. JVM probablemente gana en caliente.
- **Desarrollo rápido**: Python gana en líneas de código.
- **Plazo académico**: Python gana — la combinación OSMnx + NetworkX + FastAPI + Pydantic no tiene equivalente trivial en Java.

**Veredicto**: Python implementación primaria; Java valida correctitud del núcleo crítico. La partición refleja la realidad del ecosistema: Python tiene el ecosistema GIS, Java aporta validación estática del núcleo y verificación cruzada.

## Alternativas consideradas

### Backend completo duplicado en Java

- **Pros:** cumplimiento máximo del RT-01.
- **Contras:**
  - API REST + persistencia + adapters + dominio en ambos lenguajes.
  - Estimación honesta: +5-6 semanas adicionales sobre el plan ya tight.
  - Inviable para equipo 1-2 personas / 2 meses.
- **Por qué se descarta:** la plantilla del profesor dice "implementado **o simulado**" — el alcance mínimo del núcleo cumple el espíritu sin duplicar todo.

### OSRM externo como segunda implementación

- **Pros:** sin costo de desarrollo; OSRM está en C++.
- **Contras:**
  - El profesor pide explícitamente Java y Python en su plantilla. OSRM no es ninguno.
  - CP-01 del SRS ya usa OSRM como oracle de precisión; usarlo además como "segunda implementación del RT" es estirar el argumento.
- **Por qué se descarta:** traiciona el texto literal del requisito.

### Rust + Julia (alternativa explorada el 2026-04-16)

- **Pros:** "lenguajes matemáticos" interesantes; buen contraste SQA.
- **Contras:** el RT del profe pide Java y Python, no otros lenguajes.
- **Por qué se descarta:** no se ajusta al requisito literal.

### Solo función de costo en Java (sin triaje, sin A*)

- **Pros:** menos código.
- **Contras:**
  - Función de costo aislada no es "núcleo de cálculo" defendible.
  - Probabilidad alta de que el profesor objete el alcance reducido.
- **Por qué se descarta:** demasiado mínimo.

## Consecuencias

### Positivas

- Cumple los 4 RTs literalmente.
- Validación cruzada robusta detecta defectos que un solo lenguaje no encontraría.
- CI matriz dual eleva el rigor SQA real, no solo nominal.
- Java aporta perspectiva de tipos estáticos al diseño del dominio (puede generar mejoras retroactivas en Python si surgen ambigüedades).
- Defendible y memorable para la evaluación.

### Negativas / costo

- **+2 a 3 semanas** de trabajo (estimación honesta) para el módulo Java mínimo. Calendario sostiene este costo si Java arranca post-H2 (routing Python listo como referencia probada).
- Curva de aprendizaje de Java + Maven + JGraphT si el equipo no lo tiene fresco.
- Mantener dos implementaciones obliga a sincronizar cambios — si el dominio cambia, ambos cores se actualizan.
- CI más pesada: matriz dual + comparación = 5 jobs en pipeline.

### Neutras

- Decisión depende fuertemente de ADR-0006 (Ports & Adapters): sin `domain/` puro y aislado, portar a Java sería mucho más costoso.

## Cumplimiento / verificación

- `core-java/pom.xml` declara dependencias: JGraphT, Jackson, JUnit 5, AssertJ, JaCoCo, Spotless, Checkstyle.
- `core-java/` arranca a más tardar al cerrar H2 (`~2026-06-14` según roadmap H-J).
- `.github/workflows/ci.yml` tiene jobs: `python`, `java`, `dataset`, `compare`, `report`.
- `tools/compare_outputs.py` se ejecuta en cada push y falla si la equivalencia sale fuera de tolerancia.
- `docs/quality/rt-validation-report.md` se publica automáticamente en push a `main`.
- `docs/quality/rt-justification.md` se redacta al cierre del proyecto (H5) como entregable RT-04.
- La FTR-03 audita explícitamente el cumplimiento de los 4 RTs (`docs/quality/ftr/0003-validacion-dual-java-python.md`).

## Referencias

- Plantilla oficial del profesor: `Inbox/Plantilla_Especificación_Requisitos.doc` del vault (sección 3.2 / 3.9 — Validación del núcleo de cálculo).
- SRS vigente: `Proyectos/Sentinel-Dispatch/Entregables/SRS/SRS_Sentinel-Dispatch.tex/.pdf` del vault (pendiente restaurar sección 2.16).
- Plan B: `Proyectos/Sentinel-Dispatch/Planificación/Plan B - Reestructuración.md`.
- [ADR-0006 — Ports & Adapters](0006-ports-and-adapters.md) — habilita el portado.
- [ADR-0001 — Stack](0001-stack.md) — Python primario justificado.
- JGraphT documentation. https://jgrapht.org/
- *AStarShortestPath* class. https://jgrapht.org/javadoc/org.jgrapht.core/org/jgrapht/alg/shortestpath/AStarShortestPath.html
