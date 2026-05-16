---
adr: 0006
title: Estructura interna del monolito modular — Ports & Adapters liviano
status: accepted
date: 2026-05-15
deciders: Benjamin López
tags: [adr, arquitectura, dominio]
---

# ADR 0006 — Estructura interna del monolito modular: Ports & Adapters liviano

## Contexto

ADR-0002 fijó "monolito modular" con módulos por capacidad de negocio (`triaje/`, `routing/`, `dispatch/`, `persistence/`, `api/`, `web/`), pero **no decidió cómo se organizan internamente esos módulos**. Sin esa decisión, los tests unitarios diseñados en el entregable 2026-05-14 (UT-03/04/05/07/08/09) son difíciles de escribir:

- Cualquier función de `triaje` que use el reloj real (`datetime.now()`) vuelve los tests no deterministas.
- Cualquier función de `routing` que cargue OSMnx en el import vuelve los tests lentos (30+ segundos).
- Cualquier función que importe FastAPI o SQLAlchemy obliga a tener la BD y el servidor levantados.

Adicionalmente, ADR-0008 (validación dual Java vs Python) requiere que el núcleo de cálculo (triaje + A* + función de costo) sea aislable y portable a otro lenguaje sin arrastrar adapters de I/O.

## Decisión

Adoptamos **Ports & Adapters liviano** (también conocido como Arquitectura Hexagonal o Clean Architecture liviana) dentro del monolito modular.

Estructura concreta en `core-python/src/sentinel_dispatch/`:

```text
sentinel_dispatch/
├── domain/                      ← lógica pura, sin imports de frameworks
│   ├── triaje/                  ← árbol MPDS-subset; RespuestaTriaje; CategoriaMPDS
│   ├── routing/                 ← solver A* sobre interfaz GrafoVial
│   └── dispatch/                ← función de costo; argmin; política re-despacho
│
├── application/                 ← casos de uso (orquestan dominio + ports)
│   ├── despachar_ambulancia.py
│   ├── evaluar_redespacho.py
│   └── simular_dataset.py
│
├── ports/                       ← interfaces (Protocols / ABCs)
│   ├── grafo_vial.py            ← interfaz que routing espera
│   ├── repositorio_eventos.py   ← interfaz del log inmutable
│   └── reloj.py                 ← interfaz para inyectar tiempo
│
├── adapters/                    ← implementaciones concretas de los ports
│   ├── grafo_osmnx.py           ← lee OSMnx + NetworkX (IV Región)
│   ├── grafo_fake.py            ← grafo sintético para tests rápidos
│   ├── repositorio_jsonl.py     ← log JSONL append-only
│   └── reloj_sistema.py         ← reloj real + reloj fake para tests
│
├── interfaces/                  ← entry points
│   ├── cli/                     ← CLI (Typer / click)
│   └── api/                     ← FastAPI (mínima v1)
│
└── __init__.py                  ← __version__
```

**Regla de la flecha**: las dependencias apuntan hacia adentro.

- `domain/` no importa nada de `adapters/`, `interfaces/` ni librerías de I/O.
- `application/` usa `domain/` + `ports/`.
- `adapters/` implementan `ports/`.
- `interfaces/` invocan casos de uso de `application/` y ensamblan adapters concretos.

**Sin contenedor de inyección de dependencias**: las dependencias se inyectan a mano en los entry points (`cli/` y `api/`). Para 5 ports concretos, un contenedor formal es overhead injustificado.

## Alternativas consideradas

### Capas técnicas (controllers / services / repositories)

- **Pros:** familiar para devs con experiencia en frameworks tradicionales (Spring, .NET).
- **Contras:**
  - Agrupa por tipo técnico, no por capacidad de negocio. Choca con el "lenguaje del dominio" que pide DDD liviano.
  - `services/` se vuelve cajón de sastre.
  - Difícil de testear el dominio aislado: los services importan repositorios concretos por defecto.
- **Por qué se descarta:** convención frecuente pero inferior para sistemas con núcleo matemático claro como Sentinel.

### DDD pesado con aggregates, repositories formales, domain events, CQRS

- **Pros:** potente para sistemas con múltiples bounded contexts.
- **Contras:**
  - Sentinel tiene **un solo** bounded context (despacho).
  - Aggregates formales requieren disciplina alta sin valor agregado para 5 módulos.
  - Domain events y CQRS son maquinaria que el equipo de 2 personas no necesita en 2 meses.
- **Por qué se descarta:** YAGNI. La metodología vault explícitamente recomienda DDD **liviano**, no pesado, para proyectos chicos.

### Monolito sin estructura interna explícita ("big single package")

- **Pros:** velocidad inicial máxima.
- **Contras:**
  - En 2-3 meses se vuelve "big ball of mud".
  - Las decisiones de ADR-0008 (validación dual Java vs Python) se vuelven prácticamente imposibles: ¿qué código se porta a Java?
- **Por qué se descarta:** el costo de poner fronteras explícitas hoy es bajo y paga en testeo + portabilidad + defensa académica.

### Onion Architecture estricta (5 capas con regla rígida de no-saltarse)

- **Pros:** todavía más explícito.
- **Contras:** una capa más (`infrastructure` separada de `adapters`) que no aporta para este tamaño.
- **Por qué se descarta:** ports & adapters ya da la separación suficiente.

## Consecuencias

### Positivas

- **Tests del dominio sin I/O**: UT-03/04 (triaje) corren sin OSM, sin BD, sin FastAPI → milisegundos.
- **Reloj inyectable**: UT-05 (factor_hora a las 07:30) se prueba con `reloj_fake` sin parchar `datetime.now()`.
- **Cambio de persistencia futuro**: si JSONL (ADR-0007) se queda corto, se implementa nuevo adapter sin tocar dominio.
- **Cambio de fuente de grafo**: `grafo_osmnx.py` para producción, `grafo_fake.py` para tests, eventualmente `grafo_osrm.py` si se quiere usar OSRM nativo.
- **Portabilidad a Java**: el `core-java/` (ADR-0008) implementa el mismo `domain/` puro sobre adapters Java equivalentes. La separación hace este portado tractable.
- **Defendible académicamente**: Ports & Adapters (Cockburn 2005) y Clean Architecture (Martin 2017) son patrones reconocibles que cualquier evaluador con background en arquitectura identifica.

### Negativas / costo

- **Curva inicial**: requiere disciplina para no saltarse capas. Mitigación: code review explícito en PRs que crucen `domain/ ← adapters/`.
- **Más archivos**: cada nueva funcionalidad típicamente toca 2-3 archivos (port + adapter + caso de uso) vs 1 en una estructura plana. Compensado por la testabilidad.
- **Inyección manual de dependencias**: en `cli/main.py` y `api/main.py` hay que ensamblar adapters concretos. Es código explícito y aburrido, pero claro.

### Neutras

- La regla "domain no importa frameworks" se verifica en code review hoy; un `import-linter` con contratos declarativos se puede agregar más adelante sin disrupción.
- La separación entre `application/` y `domain/` es sutil en casos triviales. Regla práctica: si necesita un port para hacer su trabajo, va en `application/`; si es lógica pura, va en `domain/`.

## Cumplimiento / verificación

- **Estructura de carpetas**: `core-python/src/sentinel_dispatch/{domain,application,ports,adapters,interfaces}/` con `__init__.py` por paquete.
- **Tests por capa**: `core-python/tests/unit/domain/` para lógica pura; `tests/unit/application/` para casos de uso con ports mockeados; `tests/integration/adapters/` para adapters reales.
- **Code review**: rechazar PRs donde `domain/` importe de `adapters/`, `interfaces/` o librerías de I/O (OSMnx, FastAPI, SQLAlchemy, etc.).
- **Futuro**: agregar `import-linter` en CI con contratos como:
  ```yaml
  [importlinter]
  root_package = sentinel_dispatch

  [importlinter:contract:dominio-puro]
  type = forbidden
  source_modules = sentinel_dispatch.domain
  forbidden_modules = sentinel_dispatch.adapters, sentinel_dispatch.interfaces, osmnx, fastapi, sqlalchemy
  ```
- **Tests UT del entregable 2026-05-14**: UT-03, UT-04, UT-05, UT-07, UT-08, UT-09 se implementan en `tests/unit/domain/` sin requerir adapters concretos.

## Referencias

- [ADR-0001 — Stack](0001-stack.md)
- [ADR-0002 — Monolito modular](0002-monolito-modular.md)
- [ADR-0007 — Persistencia JSONL](0007-persistencia-jsonl.md)
- [ADR-0008 — Validación dual Java vs Python](0008-validacion-dual-java-python.md)
- Alistair Cockburn — *Hexagonal Architecture* (2005). https://alistair.cockburn.us/hexagonal-architecture/
- Robert C. Martin — *Clean Architecture* (Prentice Hall, 2017).
- Vaughn Vernon — *Implementing Domain-Driven Design* (Addison-Wesley, 2013), capítulo "Application Architectures".
- `Recursos/Procesos/Metodología de Proyectos/Buenas prácticas.md` del vault, sección "Clean Architecture / Hexagonal".
