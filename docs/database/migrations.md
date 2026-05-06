# Migraciones

> **Estado:** placeholder. Detalle pendiente cuando se cree la primera migración.

## Herramienta

**Alembic** ≥ 1.14 con SQLAlchemy 2.x.

## Convenciones

- Carpeta: `alembic/versions/`.
- Una migración por PR si toca esquema.
- Idempotentes y reversibles cuando sea posible.
- Test de migración up/down en CI antes del merge.

## Comandos

```bash
make db-init       # crear BD desde cero
make db-upgrade    # aplicar migraciones pendientes
make db-downgrade  # revertir última migración
```

## Generar nueva migración

```bash
uv run alembic revision --autogenerate -m "agrega tabla X"
```

Revisar siempre el diff generado antes de commit.
