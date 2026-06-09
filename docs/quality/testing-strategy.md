# Estrategia de testing

> Pirámide de pruebas adaptada al proyecto académico, sobre un núcleo de cálculo **implementado dos veces** (Python primario + Java) y validado de forma cruzada.

## Dos cores, una verdad

El requisito transversal RT-01..RT-04 exige el núcleo de cálculo en **Python y Java**. Por eso el testing tiene dos suites independientes más una verificación de equivalencia:

| Suite | Framework | Nº tests | Cobertura |
|---|---|---|---|
| **Python** (`core-python`) | pytest 8.3 + pytest-asyncio + pytest-cov + httpx | 324 | 90.33 % (gate 90 %) |
| **Java** (`core-java`) | JUnit 5 (Jupiter) + AssertJ | 186 | JaCoCo |
| **Dual RT-02** | `tools/compare_outputs.py` | 12/12 incidentes | bit-exacto |

## Capas (pirámide Python)

| Capa | Marker | Qué prueba |
|---|---|---|
| **Unit** | `unit` (en `tests/unit/`) | Lógica pura de `triaje`, `routing`, `dispatch`; casos límite y clases de equivalencia |
| **Integración** | `integration` (en `tests/integration/`) | Endpoints HTTP de la API (`httpx.AsyncClient`), adapter JSONL append-only, consola web del operador |
| **Dataset (aceptación)** | `dataset` | Los 12 incidentes del SRS sec. 2.12 end-to-end — sustituye al E2E formal |
| **Slow** | `slow` (opt-in `-m slow`) | Pruebas > 1 s: performance CP-12, eval-95 contra el fixture OSRM |

Marcadores declarados en `pyproject.toml` con `--strict-markers` (un marker no declarado es error, no warning).

## Validación dual (RT-02) — el corazón del proyecto

Ambos cores ejecutan el **mismo dataset** y emiten un JSONL por incidente con un schema congelado (ADR-0017). `tools/compare_outputs.py` los compara campo a campo:

- Resultado: **12/12 OK · 0 WARN · 0 FAIL**, paridad **bit-exacta** en rutas A\* y ETAs.
- Las diferencias estructurales previsibles (p. ej. aristas paralelas del grafo: Python `MultiDiGraph` vs Java dedup) están documentadas en ADR-0017 y SRS sec. 2.16.

```bash
make compare    # corre ambos cores + compara (es el job CI 'compare')
```

## Persistencia

El estado se guarda en **JSONL append-only** (ADR-0007, supersede a la SQLite del diseño original ADR-0003). Los tests del repositorio (`test_repositorio_jsonl_append_only.py`) verifican la inmutabilidad estructural (RN-03/RN-07): el adapter no expone `update`/`delete` y el archivo solo crece monotónicamente. Sin BD relacional ni Docker.

## Herramientas

- **Python:** pytest (+ `pytest-asyncio`, `pytest-cov`), `httpx.AsyncClient` para la API, fixtures en `tests/fixtures/` y `data/`. Lint y formato con **Ruff** (incluye reglas de seguridad `bandit`), tipos con **mypy strict** (estricto en `domain`/`application`/`ports`).
- **Java:** **JUnit 5 + AssertJ** (asserts fluidos), **JaCoCo** (cobertura), **Spotless** (Google Java Format).

## Qué NO se testea

- Frameworks de terceros (se asume que funcionan).
- Configuración trivial de Pydantic y código generado.

## Dataset de aceptación

Origen: SRS sec. 2.12. 12 incidentes I-01..I-12 que cubren las cinco categorías MPDS — Alpha (1), Bravo (2), Charlie (3), Delta (3), Echo (3) — con resultado esperado y justificación por incidente. **Cualquier cambio al dataset requiere ADR** (es contrato).

## Comandos

```bash
# Python (desde core-python/)
make test          # suite completa + cobertura (gate 90 %)
make test-fast     # solo unit, sin slow
make test-dataset  # los 12 incidentes de aceptación

# Java (desde core-java/)
mvn test

# Validación dual (desde la raíz del monorepo)
make compare
```

## CI (GitHub Actions)

Seis jobs en cada push/PR a `main`: `python-lint`, `python-typecheck`, `python-test` (con cobertura), `java-test` (Spotless + JUnit + JaCoCo), `compare` (RT-02 dual) y `security` (Gitleaks).
