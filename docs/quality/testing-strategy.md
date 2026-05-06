# Estrategia de testing

> Pirámide adaptada al proyecto académico.

## Capas

| Capa | Cobertura objetivo | Qué prueba |
|---|---|---|
| **Unit** | ≥ 70% en `triaje`, `routing`, `dispatch` | Lógica pura, casos límite, equivalence classes |
| **Integración** | ≥ 60% en `api` y `persistence` | Endpoints HTTP, BD SQLite `:memory:` |
| **Dataset** | 100% de los 12 incidentes del SRS sec. 2.12 | Validación end-to-end del comportamiento del sistema completo |

## Sin E2E formal

El **dataset de aceptación** sustituye la capa E2E tradicional. Se ejecuta con:

```bash
make test-dataset
```

## Herramientas

- `pytest` ≥ 8.3 + `pytest-asyncio` + `pytest-cov`.
- `httpx.AsyncClient` para tests de API.
- SQLite `:memory:` para integración (sin Docker).
- Fixtures versionadas en `tests/fixtures/`.

## Markers

- `@pytest.mark.unit` (implícito si está en `tests/unit/`)
- `@pytest.mark.integration` (en `tests/integration/`)
- `@pytest.mark.dataset` (los 12 incidentes del SRS)
- `@pytest.mark.slow` (>1 s, opt-in con `-m slow`)

## Qué NO testear

- Frameworks de terceros (asume que funcionan).
- Getters/setters triviales de SQLAlchemy.
- Configuración de Pydantic.

## Dataset de aceptación

Origen: SRS sec. 2.12. 12 incidentes I-01..I-12 cubriendo Alpha (1), Bravo (2), Charlie (3), Delta (3), Echo (3). Resultado esperado documentado por incidente con justificación.

Cualquier cambio al dataset requiere ADR (es contrato).
