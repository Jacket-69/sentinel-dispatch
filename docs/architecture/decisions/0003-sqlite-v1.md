---
adr: 0003
title: SQLite + SQLAlchemy 2.x + Alembic para v1, plan de migración a Postgres documentado
status: superseded
superseded-by: 0007
date: 2026-05-06
superseded-date: 2026-05-15
deciders: Benjamin López
tags: [adr, persistencia, superseded]
---

# ADR 0003 — SQLite + SQLAlchemy 2.x + Alembic para v1

> **⚠ SUPERSEDED el 2026-05-15 por [ADR-0007 — Persistencia JSONL append-only](0007-persistencia-jsonl.md).**
>
> Razón del cambio: para 12 incidentes del dataset y un único operador, SQLAlchemy 2.x async + Alembic + triggers SQL es sobreingeniería. ADR-0007 implementa el log inmutable mediante JSONL append-only, manteniendo el cumplimiento de RN-03 y RN-07 sin la maquinaria SQL. El plan de migración a SQL queda documentado en ADR-0007 si llegara a ser necesario.
>
> Este ADR se conserva como historia. **No usar como referencia activa.**

## Contexto

Sentinel-Dispatch necesita persistir:

- **Inventario de unidades** (~10 unidades, lectura frecuente, escritura rara).
- **Incidentes** (escritura por evento; volumen del dataset = 12).
- **Despachos** (escritura por confirmación de operador).
- **Log inmutable de eventos** (RN-03, RN-07): append-only, frecuencia de escritura igual a la de despachos + cancelaciones + finalizaciones + re-despachos.

Carga real esperada: 1 operador concurrente, escrituras del orden de decenas por hora en el peor caso académico, lecturas del orden de cientos por hora (panel de unidades, dashboard). El SRS (sec. 2.10 Trazabilidad) exige persistencia transaccional con invariantes de dominio.

El proyecto vive 2 meses, sin staging/prod separados, en demo local (Cloudflare Tunnel desde PC, ver ADR-0005).

## Decisión

Usamos **SQLite 3** + **SQLAlchemy 2.x async** + **Alembic** + **aiosqlite** como capa de persistencia para v1.

- **Archivo único**: `data/sentinel.db`. Sin servidor de BD.
- **SQLAlchemy 2.x estilo declarativo nuevo** con `AsyncSession`.
- **Alembic** para migraciones versionadas desde el día 1.
- **`aiosqlite`** como driver async para que FastAPI no bloquee el loop.
- **Log inmutable** implementado vía constraint de aplicación + trigger SQL que rechaza UPDATE/DELETE sobre `event_log`.
- **Backups**: copia diaria del archivo `.db` a `~/backups/sentinel-dispatch/` (ver `docs/database/backup-policy.md`).

## Plan de migración a PostgreSQL (cuándo y cómo)

Si en algún momento se rompe alguna de estas premisas, migramos a Postgres:

| Disparador | Por qué SQLite deja de servir |
|---|---|
| >1 operador concurrente con escrituras simultáneas | SQLite serializa escrituras; aparecerán "database is locked" |
| Despliegue en cloud con múltiples instancias detrás de balanceador | El archivo .db es local a la VM; no comparte estado |
| Necesidad de queries analíticas pesadas sobre log inmutable | Postgres tiene window functions, índices avanzados, planner mejor |
| Auditoría externa que requiera roles/permisos a nivel BD | SQLite tiene seguridad granular pobre |

**Cómo migramos** (aproximadamente):

1. Cambiar `DATABASE_URL` en `.env` a `postgresql+asyncpg://...`.
2. Reemplazar driver `aiosqlite` → `asyncpg` en `pyproject.toml`.
3. Revisar tipos: `JSON` → `JSONB`, `BLOB` → `BYTEA`.
4. Re-generar baseline de Alembic contra Postgres vacío.
5. Cargar dump SQL del SQLite a Postgres con script de transferencia (las entidades son chicas, un script Python de 50 líneas sirve).
6. Ajustar tests de integración para que usen Postgres con `testcontainers` en CI (en local, mantener SQLite `:memory:` por velocidad).

**Estimación de costo de migración** si se hace correctamente: 1–2 días de trabajo para 1 persona. Por eso es razonable empezar en SQLite.

## Alternativas consideradas

### PostgreSQL desde el día 1
- **Pros:**
  - No hay migración futura.
  - Tipos más ricos (JSONB, arrays, range types).
  - Concurrencia real.
- **Contras:**
  - Requiere Docker compose o servicio externo en local; agrega un container más al runbook.
  - El operador típico que clone el repo necesita levantar Postgres antes de poder correr `make dev`.
  - Para 10 unidades + 12 incidentes del dataset, es **overkill** medible.
- **Por qué se descarta:** overhead operacional sin beneficio real en v1.

### MongoDB / NoSQL
- **Pros:**
  - Schema flexible.
  - El "log inmutable JSON" calza con el modelo documento.
- **Contras:**
  - Las entidades del dominio (Unidad ↔ Despacho ↔ Incidente) tienen relaciones; SQL es la opción honesta.
  - Transacciones ACID multi-documento son complicadas.
  - Sin migraciones versionadas estándar.
- **Por qué se descarta:** los datos son relacionales; usar NoSQL es luchar contra el modelo.

### TinyDB / archivo JSON
- **Pros:** simplicidad extrema.
- **Contras:** sin transacciones reales, sin integridad referencial, sin migraciones, sin queries decentes.
- **Por qué se descarta:** R-04 del SRS (confusión de unidades) exige tipos fuertes y validación; TinyDB no da garantías.

### DuckDB
- **Pros:** SQL completo en archivo, muy rápido para analítica.
- **Contras:** orientado a OLAP; escritura concurrente es punto débil; ecosystem ORM aún tibio.
- **Por qué se descarta:** Sentinel es OLTP (transacciones) más que OLAP. SQLite cubre mejor el patrón de escritura.

## Consecuencias

### Positivas
- **Setup local trivial**: `make db-init` y listo. No hay container de BD.
- **Testing rápido**: SQLite `:memory:` para tests integración sin Docker.
- **Backup trivial**: `cp data/sentinel.db ~/backups/...`.
- **Curva de aprendizaje del equipo**: SQLAlchemy 2.x + Alembic son skills transferibles a cualquier stack Python serio.

### Negativas / costo
- **Concurrencia de escritura limitada**: SQLite serializa. No es problema con 1 operador, sí lo sería en producción real.
- **Sin tipos JSON nativos avanzados**: el log inmutable se persiste como `JSON` (texto serializado). Para queries sobre el contenido del JSON usaremos `json_extract()` de SQLite, que funciona pero es menos potente que JSONB de Postgres.
- **Migración futura es posible pero no es gratis**: 1–2 días de trabajo si llega el caso.

### Neutras
- El esquema vive en código (SQLAlchemy declarativo) + migraciones Alembic; cambios al esquema requieren `alembic revision --autogenerate -m "..."` + revisión manual del diff.

## Cumplimiento / verificación

- `pyproject.toml` declara `sqlalchemy>=2.0`, `alembic>=1.14`, `aiosqlite>=0.20`.
- `make db-init`, `make db-upgrade`, `make db-downgrade` funcionan.
- Tests de integración corren contra SQLite `:memory:` (rápido, reproducible).
- DoD requiere migración Alembic en el mismo PR si se cambia esquema.
- El log inmutable tiene **trigger SQL** que rechaza UPDATE/DELETE; un test de integración valida que el rechazo ocurre.
- Backup diario verificado mensualmente con restauración real (ver `docs/database/backup-policy.md`).

## Referencias

- [SRS — sec. 2.10 Trazabilidad, RN-03, RN-07](../../requirements/requirements.md)
- [SQLite — When To Use](https://www.sqlite.org/whentouse.html) — guía oficial de cuándo SQLite es apropiado.
- [SQLAlchemy 2.0 — async ORM](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Alembic — autogenerate](https://alembic.sqlalchemy.org/en/latest/autogenerate.html)
- [ADR-0001 — Stack](0001-stack.md)
- [ADR-0002 — Monolito modular](0002-monolito-modular.md)
