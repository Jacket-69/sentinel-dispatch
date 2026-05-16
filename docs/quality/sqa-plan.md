# Plan SQA — Sentinel-Dispatch

> Versión 1.0 · 2026-05-15 · autor: Benjamín López · ramo GCS — UCEN 2026-S1 — Prof. G. Honores.

Este documento define cómo se asegura la calidad del proyecto. Es **un mapa, no un manual**: las prácticas operativas viven en otros documentos referenciados. Aquí van solo las decisiones específicas de Sentinel-Dispatch que no caben en otro lado.

## Alcance

- Cubre el proyecto desde F0 (cerrada) hasta F6 (cierre 2026-07-15).
- Aplica a `core-python/` (implementación primaria) y `core-java/` (validación dual mínima — núcleo de cálculo).
- **Fuera de alcance**: operación 24/7 real, certificación clínica MPDS, auditoría externa, MEXCLP (R-03 del SRS).

## Roles

| Rol | Persona | Deber principal |
|---|---|---|
| SQA Lead | Benjamín López | Mantener plan vigente, aprobar/rechazar PRs según DoD, moderar FTR, decidir en conflictos. Representa al "cliente" (SAMU) en revisiones. |
| Integrante | Fernando Godoy M. | Implementa historias, revisa PRs cuando esté disponible, participa como par en FTR. |

## Dónde vive cada cosa (mapa de referencias)

| Tema | Documento autoritativo |
|---|---|
| Requisitos, reglas de negocio, dataset, RT-01..RT-04 | `docs/SRS.md` (espejo Markdown) + `SRS_Sentinel-Dispatch.tex/.pdf` (entregable formal en vault) |
| Estado del proyecto + hitos + próximos pasos | `Proyectos/Sentinel-Dispatch/Planificación/Plan B - Reestructuración.md` (vault) |
| Decisiones costosas de revertir | `docs/architecture/decisions/NNNN-*.md` (ADRs) |
| Definition of Done — criterio bloqueante por PR | `docs/quality/definition-of-done.md` |
| Pirámide y cobertura objetivo | `docs/quality/testing-strategy.md` |
| Marco metodológico (DORA, Twelve-Factor, ISO 9001) | `Recursos/Procesos/Metodología de Proyectos/` (vault) — no se duplica acá |
| Casos UT/IT diseñados (entregable 14-may) | `Proyectos/Sentinel-Dispatch/Entregables/Pruebas 2026-05-14/` (vault) |
| Bitácora y log meta | `bitácora.md` del proyecto + `_meta/log.md` del vault |

## Actividades del SQA Group (Clase 04) — mapeo

Las seis actividades canónicas materializadas en este proyecto. **Sin duplicar lo que ya vive en otro documento.**

| Actividad Clase 04 | Materialización concreta | Evidencia |
|---|---|---|
| 1. Plan SQA | Este documento | Historial Git |
| 2. Diseño del proceso | Metodología aplicada del vault + Plan B (no se reinventa por sesión) | Documentos referenciados |
| 3. Monitoreo del proceso | CI (GitHub Actions: ruff/mypy/pytest + spotless/JUnit + compare dual) + pre-commit (gitleaks) + branch protection en `main` | Logs GitHub Actions |
| 4. Auditoría de productos | 3 FTR planificadas (ver tabla siguiente) | Actas en `docs/quality/ftr/NNNN-*.md` |
| 5. Casos de prueba | UT/IT del entregable 14-may + dataset 12 incidentes del SRS sec. 2.12 | `tests/` en ambos cores + `data/dataset/` |
| 6. Ejecución | `make test-python`, `make test-java`, `make test-dataset`, `make compare` | Pipeline CI |

## Revisiones Técnicas Formales (FTR)

Aplican directrices canónicas de la Clase 04: revisar producto no productor, preparación previa obligatoria, ≤90 min, enunciar problemas sin resolverlos en la reunión, acta firmada.

| FTR | Producto auditado | Fecha | Hito |
|---|---|---|---|
| **FTR-01** | A* + interfaz `GrafoVial` (`core-python/.../domain/routing/`) | ~2026-06-14 | Cierre H2 |
| **FTR-02** | Función de costo + política re-despacho (`core-python/.../domain/dispatch/`) | ~2026-06-28 | Cierre H3 |
| **FTR-03** | Núcleo Java + reporte de equivalencia dual (cumplimiento RT-01..RT-04) | ~2026-07-07 | Cierre H3-J |

**Formato del acta**: ver `docs/quality/ftr/0000-template.md`. Cada hallazgo se clasifica por **severidad** (crítico bloquea merge, mayor bloquea cierre de hito, menor va al backlog) y **tipo** (defecto, mejora, pregunta).

## Validación dual Java vs Python (RT-01..RT-04)

Decisión completa en [ADR-0008](../architecture/decisions/0008-validacion-dual-java-python.md). Mecanismo operativo:

- `core-python/` ejecuta el dataset → JSON outputs.
- `core-java/` ejecuta el mismo dataset (núcleo: triaje + A* + función de costo, leyendo el mismo `coquimbo.graphml`) → JSON outputs.
- `tools/compare_outputs.py` compara con tolerancias:

| Campo | Tolerancia |
|---|---|
| `categoria_mpds`, `unidad.id`, `despacho_suboptimo` | exact match |
| `eta_segundos`, `costo.T_viaje`, `costo.total` | ±5% |
| `ruta` (lista nodos) | mismo origen/destino, longitud ±10% |

- Reporte automático en `docs/quality/rt-validation-report.md`.
- Justificación RT-04 ("cuál implementación es más adecuada") en `docs/quality/rt-justification.md` al cierre del proyecto.

## Trazabilidad RF → Test

La matriz vive como **tabla en el SRS** (`docs/SRS.md`, sección de trazabilidad) actualizada al cierre de cada hito. No se duplica acá. CI la valida automáticamente: cada RF crítico debe tener al menos un test que lo cite en su docstring.

## Control de defectos

Defectos detectados se registran como issues en GitHub con labels:

- `severity:critical|major|minor`
- `origin:dominio|adapter|interfaz|config`

Al cierre del proyecto se hace un **Pareto** de origen si hay ≥10 defectos cerrados. Si hay menos, se documenta como limitación honesta (n insuficiente para análisis estadístico).

## Justificación de decisiones de calidad

Lo que el profe evalúa explícitamente en las entregas. Decisiones tomadas y por qué:

- **Ports & Adapters liviano** (ADR-0006): permite testear el dominio sin OSM/BD/FastAPI; tests UT son rápidos y aislados.
- **JSONL append-only** (ADR-0007, supersede ADR-0003): inmutabilidad por construcción para RN-03/07 sin overhead de SQL para 12 incidentes.
- **Validación dual Java vs Python** (ADR-0008): cumple RT-01..RT-04 con alcance mínimo defendible; `core-java/` solo núcleo, no backend completo.
- **DoD recortado**: criterios bloqueantes proporcionales a equipo de 2 personas / 2 meses; el frame industrial completo es opt-in.
- **FTR por hito crítico** (no calendarizado fijo): 3 FTR cubren A*, función de costo y validación dual — los productos de mayor riesgo. Documentación declarativa se revisa en PR estándar.

## Vida del plan

- Vivo en F3–F5. Se actualiza al cierre de cada hito o cuando un ADR nuevo afecta SQA.
- Cambios al plan: PR aprobado por SQA Lead.
- Congelado al cierre del proyecto (F6, 2026-07-15) como entregable.
