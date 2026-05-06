# Coding standards — Sentinel-Dispatch

## Estilo

- **Ruff** decide formato y lint. Si `ruff format` lo cambia, está bien.
- **Mypy strict** en módulos de dominio (`triaje`, `routing`, `dispatch`).
- **PEP 8** + naming PEP 8 (snake_case funciones/variables, PascalCase clases, UPPER_SNAKE constantes).

## Naming del dominio

Usar el lenguaje del glosario (`docs/product/glossary.md`). No `Item`, `Type`, `Object` genéricos:

```python
# Mal
def calcular(item: dict) -> int: ...

# Bien
def calcular_costo(unidad: Unidad, incidente: Incidente) -> Costo: ...
```

## Magnitudes físicas

Internamente: distancias en metros, tiempos en segundos, velocidades en m/s. Conversión solo en el borde (UI/OSM input).

Considerar `NewType` para evitar mezclas:

```python
from typing import NewType

Metros = NewType("Metros", float)
Segundos = NewType("Segundos", int)
MetrosPorSegundo = NewType("MetrosPorSegundo", float)
```

## Logs

`structlog`, eventos namespaced, nunca `print()` en producción.

```python
import structlog
log = structlog.get_logger()

log.info("dispatch.created", incident_id=i.id, unit_id=u.id, eta_seconds=eta)
```

## Async

FastAPI nativo async. Usar `aiosqlite` + `AsyncSession` de SQLAlchemy. No mezclar sync con async sin razón.

## Tests

Un archivo por módulo testeado:

- `tests/unit/triaje/test_arbol_mpds.py` testea `src/sentinel_dispatch/triaje/arbol.py`.

Naming: `test_<comportamiento_esperado>_<contexto>` (no `test_func_1`).
