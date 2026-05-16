---
adr: 0007
title: Persistencia JSONL append-only para v1 (reemplaza ADR-0003)
status: accepted
date: 2026-05-15
deciders: Benjamin López
tags: [adr, persistencia, supersede]
supersedes: 0003
---

# ADR 0007 — Persistencia JSONL append-only para v1

> Reemplaza [ADR-0003 — SQLite + SQLAlchemy 2.x + Alembic](0003-sqlite-v1.md), que queda marcado `superseded`.

## Contexto

ADR-0003 había decidido SQLite + SQLAlchemy 2.x async + Alembic + `aiosqlite` + triggers SQL para implementar el log inmutable de eventos exigido por RN-03 y RN-07. La decisión fue racional para un proyecto industrial pero **sobreingeniería para Sentinel**:

- El dataset de aceptación tiene **12 incidentes** (SRS sec. 2.12).
- Las entidades persistidas son: incidentes (~12), despachos (~12-15), eventos de log (~30-50 por simulación completa).
- 1 operador concurrente; sin escrituras concurrentes reales.
- El sistema vive **2 meses** académicos y se archiva al cierre del semestre. No hay operación 24/7 ni stakeholders externos que dependan de él.

La revisión 2026-05-15 (ver `Plan B - Reestructuración.md` del vault) detectó que el costo cognitivo de mantener Alembic + triggers + SQLAlchemy async se restaba al tiempo disponible para el algoritmo A* y la validación dual Java vs Python (RT-01..RT-04), que son las cosas que el profesor evalúa.

## Decisión

Para v1 usamos **JSONL append-only en disco** como mecanismo de persistencia.

- **Archivo único**: `data/eventos.jsonl`. Una línea = un evento.
- **Schema** validado con Pydantic en escritura. Tipos discriminados por campo `type` (`despacho_creado`, `despacho_cancelado`, `redespacho_propuesto`, `redespacho_confirmado`, `redespacho_rechazado`, `unidad_actualizada`).
- **Inmutabilidad por construcción**: append puro vía `open(..., "a")`. Operaciones de modificación / eliminación **no existen** en el código del adapter. RN-03 y RN-07 se cumplen estructuralmente, sin necesidad de triggers.
- **Lectura**: streaming del archivo línea a línea con `jsonlines` (o `for line in open(...)`). Filtrado en memoria con generadores. Suficiente para el volumen del proyecto.
- **Backup**: copia atómica del archivo (`cp data/eventos.jsonl backups/eventos-YYYYMMDD.jsonl`).
- **Inventario de unidades y dataset de incidentes**: en archivos JSON estáticos (`data/dataset/unidades.json`, `data/dataset/incidentes.json`), no en BD. El estado de las unidades durante la simulación vive en memoria.

El port `RepositorioEventos` (ver ADR-0006) define la interfaz; el adapter `JSONLRepositorioEventos` la implementa.

## Plan de migración a SQL (si llega el caso)

Si en algún momento se rompe alguna premisa, migramos a Postgres:

| Disparador | Por qué JSONL deja de servir |
|---|---|
| Operación con >1 operador concurrente con escrituras simultáneas | JSONL no tiene control de concurrencia atomic; necesita lock externo |
| Volumen de eventos > 100.000 | Lectura full-scan se vuelve lenta para filtros frecuentes |
| Necesidad de queries analíticas complejas | JSONL no tiene índices ni window functions |
| Auditoría externa que requiera roles/permisos a nivel BD | JSONL es archivo plano |

**Cómo migramos** (script estimado 30 líneas Python):

1. Leer `eventos.jsonl` línea a línea.
2. Para cada evento, crear fila en tabla `event_log` con columna `payload` (JSONB).
3. Generar baseline Alembic.
4. Reemplazar `JSONLRepositorioEventos` por nuevo `SQLRepositorioEventos` que implementa el mismo port.
5. `domain/` y `application/` no cambian (ADR-0006).

Estimación de costo de migración: **1 día** para 1 persona. Lo razonable es empezar simple y migrar cuando duela.

## Alternativas consideradas

### Mantener ADR-0003 (SQLite + SQLAlchemy 2.x async + Alembic + triggers)

- **Pros:**
  - Migración futura a Postgres es swap de URL.
  - Tipos fuertes mediante SQLAlchemy declarativo.
  - Inmutabilidad reforzada por trigger SQL.
- **Contras:**
  - Overhead de configuración: archivo `alembic.ini`, primera migración baseline, configuración async engine.
  - Curva de aprendizaje SQLAlchemy 2.x async para el equipo.
  - Tests requieren montar SQLite `:memory:` o gestionar fixtures de BD.
  - Para 12 incidentes, todo esto es overkill medible.
- **Por qué se descarta:** complejidad sin beneficio en el horizonte del proyecto.

### PostgreSQL desde el día 1

- **Pros:** sin migración futura, tipos ricos (JSONB), concurrencia real.
- **Contras:**
  - Requiere Docker compose con container BD; `make dev` se vuelve más pesado.
  - Operador típico que clone el repo necesita Postgres antes de correr.
  - Aún más overkill que SQLite para el volumen del proyecto.
- **Por qué se descarta:** ROI académico negativo.

### TinyDB / JSON único con todo el estado

- **Pros:** simplicidad extrema.
- **Contras:**
  - Estructura monolítica no es append-only natural; cada operación reescribe el archivo entero.
  - Riesgo de corrupción si se escribe a mitad.
- **Por qué se descarta:** JSONL es estrictamente mejor para "log inmutable" sin agregar complejidad.

### DuckDB embebido

- **Pros:** SQL completo en archivo único, muy rápido en analítica.
- **Contras:** orientado a OLAP; escritura concurrente es punto débil; ecosystem ORM tibio.
- **Por qué se descarta:** Sentinel es OLTP (escritura por evento), no analítico.

### EventStore / mensajería real

- **Pros:** estándar industrial para event sourcing.
- **Contras:** dependencia externa pesada; aprendizaje significativo; cero ROI para 12 incidentes.
- **Por qué se descarta:** YAGNI fuerte.

## Consecuencias

### Positivas

- **Setup local trivial**: no hay container de BD, no hay `make db-init`, no hay Alembic.
- **Testing rápido**: tests de adapter usan `tmp_path` de pytest; nada de Docker.
- **Backup trivial**: `cp data/eventos.jsonl backups/...`.
- **Inmutabilidad estructural**: el código no contiene UPDATE ni DELETE; un evento agregado por error solo se "corrige" con un evento `correccion` posterior — exactamente lo que la auditoría clínica exige.
- **Cumplimiento RN-03 y RN-07** sin maquinaria SQL.
- **Defensa académica**: el log JSONL append-only es patrón estándar de event sourcing simple, reconocible y citable (Fowler, "Event Sourcing").

### Negativas / costo

- **Sin índices**: filtros por `incident_id` o `unit_id` requieren scan lineal del archivo. Para 12 incidentes (~30-50 eventos) es instantáneo; para 100K eventos sería notable. No es nuestro caso.
- **Sin transacciones multi-evento atómicas**: si una operación produce 2 eventos (`despacho_creado` + `unidad_actualizada`), el segundo puede fallar después del primero. Mitigación: el orden de escritura es siempre "primero el evento que persiste decisión, después el evento que actualiza estado", y la consistencia se reconstruye al leer desde el log.
- **Migración futura sí cuesta**, aunque poco: ~1 día estimado si llega el caso.

### Neutras

- El archivo `data/eventos.jsonl` se versiona en `.gitignore` (es estado runtime, no código). El dataset estático sí se versiona (`data/dataset/incidentes.json`, `data/dataset/unidades.json`).
- La eliminación de SQLAlchemy / Alembic / aiosqlite del `pyproject.toml` reduce dependencias en ~5 paquetes.

## Cumplimiento / verificación

- `core-python/pyproject.toml` declara `jsonlines>=4.0` (o uso directo de stdlib `json`).
- `core-python/src/sentinel_dispatch/adapters/repositorio_jsonl.py` implementa el port `RepositorioEventos` (ADR-0006).
- Tests de integración escriben/leen sobre `tmp_path` (pytest fixture).
- Tests de unidad del adapter verifican que el método de escritura solo hace append y que no expone API de UPDATE/DELETE.
- `docs/data-model.md` documenta las entidades persistidas y la estructura JSON de cada tipo de evento.

## Referencias

- [ADR-0003 — SQLite v1](0003-sqlite-v1.md) — superseded por este ADR.
- [ADR-0006 — Ports & Adapters](0006-ports-and-adapters.md) — define el port `RepositorioEventos`.
- [SRS](../../SRS.md) — RN-03 (log inmutable) y RN-07 (append-only de logs).
- Martin Fowler — *Event Sourcing*. https://martinfowler.com/eaaDev/EventSourcing.html
- `jsonlines` package documentation. https://jsonlines.readthedocs.io/
