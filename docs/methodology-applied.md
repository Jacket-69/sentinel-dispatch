# Metodología aplicada — Sentinel-Dispatch

> Canónico en el repo desde **2026-06-10**. Supersede a
> `~/Documentos/CELAENO/Universidad/2026-1/Gestión de Calidad del Software/Sentinel-Dispatch/Planificación/Metodología aplicada.md`
> del vault, que queda marcado histórico (escrito el 2026-05-06, parcialmente desactualizado tras H0 el 2026-05-15).

---

- **Talla:** M · Estándar
- **Tipo:** Backend HTTP propio (FastAPI + consola web HTMX; monorepo Python + Java)
- **Proceso:** Scrumban (iteraciones académicas H0..H5; tablero GitHub Projects)
- **Estilo:** Monolito modular + Ports & Adapters liviano (ver [ADR-0006](architecture/decisions/0006-ports-and-adapters.md))
- **Fuente canónica de la metodología:** vault › `Conocimiento/Procesos/Metodología de Proyectos`

---

## Las 5 decisiones

### 1. Talla — M · Estándar

Proyecto académico semestral (~10 semanas, equipo 1–2 personas). La talla M activa el esqueleto completo de docs sin los artefactos de operación 24/7 (runbook de guardia, SLO, Dependabot, DORA metrics). Se escala a L solo si el proyecto se promueve más allá del ramo, lo cual está explícitamente descartado.

### 2. Tipo — Backend HTTP propio

FastAPI sirve tanto la API REST como los templates Jinja2 de la consola web (HTMX + Leaflet). El monorepo incluye `core-java/` como validador del núcleo de cálculo (requisito académico RT-01..RT-04), no como servicio independiente. La combinación Python principal + Java de validación es una característica particular de este proyecto sin equivalente directo en la matriz de tipos; se trata como Backend HTTP con capa de validación dual agregada.

### 3. Proceso — Scrumban

Iteraciones académicas con hitos fijos (H0..H5) como Sprints de duración variable. Sin standup formal (equipo de 2 con alta comunicación directa). Backlog en GitHub Projects. El cadence lo fija el calendario del ramo, no una retrospectiva de velocidad.

### 4. Estilo de arquitectura — Monolito modular + Ports & Adapters liviano

ADR-0002 decidió monolito modular sobre microservicios (equipo de 2, grafo OSM en RAM, plazo 10 semanas). ADR-0006 añadió la estructura interna de Ports & Adapters:

```
domain/          ← lógica pura (triaje, routing, dispatch)
application/     ← casos de uso (orquestan domain + ports)
ports/           ← interfaces (Protocols)
adapters/        ← implementaciones (OSMnx, JSONL, fake para tests)
interfaces/      ← entry points (CLI, API + templates)
```

No se adoptó DDD pesado (aggregates, CQRS, domain events): el sistema tiene un único bounded context (despacho) y 5 módulos con fronteras estables. Ver ADR-0001 para el stack completo.

### 5. Subset de docs

Según talla M para un Backend HTTP académico. Los docs del repo son los que sobrevivieron la auditoría H0 (33 → 18 archivos → hoy ~45 con ADRs y artefactos de calidad crecidos con el proyecto).

---

## Docs activos

- [x] `README.md` — showcase público + arquitectura + cómo correr
- [x] `docs/methodology-applied.md` — este archivo
- [x] `docs/quality/definition-of-done.md` — DoD académico recortado
- [x] CI mínimo (lint + typecheck + test + compare) — `.github/workflows/ci.yml`
- [x] `docs/architecture/decisions/` — 22 ADRs (0001..0022)
- [x] `docs/architecture/c4.md` — vistas C4 + BPMN
- [x] `docs/architecture/overview.md` — descripción textual
- [x] `docs/quality/sqa-plan.md` — plan SQA compacto (95 líneas, es mapa de referencias)
- [x] `docs/quality/testing-strategy.md` — pirámide adaptada
- [x] `docs/coding-standards.md` — convenciones Python + naming del dominio
- [x] `docs/devops.md` — branching + CI/CD
- [x] `docs/security.md` — baseline + threat model académico
- [x] `docs/SRS.md` — espejo Markdown del SRS LaTeX (fuente en vault)
- [x] `docs/api.yaml` — contrato OpenAPI
- [x] `docs/data-model.md` — entidades del dominio
- [x] `docs/quality/trazabilidad.md` — RF/RN/RT × módulos × CPs
- [x] `docs/quality/ftr/` — actas FTR (FTR-03 de H4 ejecutada)
- [x] `CHANGELOG.md` — una entrada por entrega académica (Keep a Changelog)
- [ ] `docs/quality/exit-notes.md` — se crea al cierre H5 con cumplimiento RFs + lecciones

**No están** (descartados en auditoría H0 o fuera del scope académico):
- `docs/operations/` (no hay oncall real)
- `docs/database/` (persistencia JSONL, no hay BD relacional)
- `docs/product/` (vision.md, glossary, mockups — consolidados en SRS y README)
- `incident-response.md`, `secrets-management.md`, `release-process.md`
- OWASP SAMM, métricas DORA, Dependabot

---

## Desviaciones del default

Las siguientes desviaciones están justificadas por el contexto académico o por decisiones explícitas del proyecto:

1. **Validación dual Java obligatoria (no es default de Backend HTTP).**
   El profesor exige implementar el núcleo de cálculo en Java + Python (RT-01..RT-04). Materializado en `core-java/` como validador con paridad RT-02 (12/12 bit-exacto). Ver ADR-0008.

2. **SRS LaTeX como entregable congelado.**
   El SRS es un artefacto de evaluación académica; no se reescribe post-entrega. Los ajustes post-implementación van vía §2.17 Addendum (ADR no aplica; es decisión de proceso). El espejo `docs/SRS.md` sí es editable.

3. **DoD académico simplificado.**
   Sin code review bloqueante obligatorio entre pares (Fernando no siempre disponible). Se reemplaza con FTRs documentadas (ver `docs/quality/ftr/`). Sin pair programming formal.

4. **CHANGELOG por entrega académica**, no por release semántica continua.
   `v0.X` durante el semestre; `v1.0.0-final` al cierre.

5. **Sin staging/prod separados.**
   Solo local + demo (deploy único para defensa oral el 2026-06-15). Ver ADR-0005.

6. **Criterios de calidad recalibrados post-evidencia (no es relajación arbitraria).**
   CP-01c → CP-01c' (±30%/≥75 en lugar de ±5%/≥95): brecha estructural vs `car.lua` de OSRM documentada en ADR-0021. CP-12 → ≤2000 ms p95 en lugar de ≤1000 ms: medición real p95=1941 ms documentada en ADR-0019. El §2.17 del SRS narra la reconciliación original → vigente.

7. **Frontend en `interfaces/api/` con estado en memoria.**
   La vista de despacho mantiene un overlay `app.state.estados_unidades` que no persiste. Conveniencia de la capa de interfaces para la demo; no modifica el dominio ni RT-02. Ver ADR-0022.

8. **`docs/methodology-applied.md` supersede al doc del vault.**
   El doc del vault (`Planificación/Metodología aplicada.md`) fue escrito el 2026-05-06 y quedó parcialmente desactualizado tras la cirugía H0 del 2026-05-15. La verdad estructural es el repo; ese doc del vault queda marcado histórico.
