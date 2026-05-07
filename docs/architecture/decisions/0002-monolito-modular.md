---
adr: 0002
title: Monolito modular sobre microservicios
status: accepted
date: 2026-05-06
deciders: Benjamin López
tags: [adr, arquitectura]
---

# ADR 0002 — Monolito modular sobre microservicios

## Contexto

Sentinel-Dispatch tiene cinco capacidades de negocio claras: **triaje**, **ruteo (A*)**, **despacho (costo + selección)**, **persistencia (log inmutable)** y **api/web (frontend operador)**. La frontera entre ellas es estable y derivada del SRS. La pregunta es si esas capacidades viven como módulos dentro de un proceso único o como servicios desplegables independientes.

El equipo es de 1–2 personas (Benjamin + Fernando), el plazo son ~10 semanas (mayo–julio 2026), no hay operación 24/7 real, y el grafo OSM (~30–60 MB en RAM) es el componente más pesado del sistema y debe estar disponible en el proceso que ejecuta el A*.

## Decisión

Adoptamos **monolito modular** desplegado como un único proceso FastAPI.

- **Un único deployable**: imagen Docker con todo dentro.
- **Módulos por capacidad de negocio** dentro de `src/sentinel_dispatch/`: `triaje/`, `routing/`, `dispatch/`, `persistence/`, `api/`, `web/`.
- **Fronteras explícitas** entre módulos: cada módulo expone una interfaz pública (clases/funciones del `__init__.py`) y los demás importan solo desde ahí.
- **No hay framework de comunicación inter-módulos**: llamadas Python directas, síncronas o async según corresponda.
- **Tests por módulo**: `tests/unit/<modulo>/` espejea la estructura.

## Alternativas consideradas

### Microservicios independientes (Triaje, Routing, Dispatch, Persistence, API gateway)
- **Pros:**
  - Escalado independiente del Routing (A* es lo más caro).
  - Aislamiento de fallos por servicio.
  - Cada servicio puede usar lenguaje distinto en teoría.
- **Contras:**
  - Operar 5 servicios con 1 persona es overhead absurdo: 5× CI, 5× observabilidad, 5× despliegues.
  - Routing necesita el grafo OSM en RAM (30–60 MB); duplicarlo entre microservicios o servirlo por red anula el sentido del A* rápido.
  - Latencia adicional por hops de red en una operación que el SRS exige completar en ≤1 s.
- **Por qué se descarta:** prematuro para el equipo, plazo y patrones de carga reales.

### Monolito sin estructura modular ("big single package")
- **Pros:**
  - Velocidad inicial de desarrollo aún mayor.
- **Contras:**
  - En 6 meses se vuelve "big ball of mud"; el dominio se acopla por accidente y no por diseño.
  - DDD liviano (lenguaje del dominio + módulos por capacidad) deja de ser posible.
  - Refactor a microservicios queda inviable.
- **Por qué se descarta:** el costo de poner fronteras explícitas hoy es bajo y paga en defensa académica + cualquier extensión futura.

### Modular monolith con event bus interno (mediator pattern)
- **Pros:**
  - Acoplamiento aún menor; módulos hablan via eventos in-process.
- **Contras:**
  - Indirección sin valor real para 5 módulos con interfaces estables.
  - Debugging más difícil (stacktraces atravesando un dispatcher).
- **Por qué se descarta:** YAGNI.

## Consecuencias

### Positivas
- Un único CI, una única observabilidad, un único runbook.
- Latencia mínima entre módulos (llamadas Python directas).
- Refactor a microservicios sigue **viable** en el futuro porque las fronteras están explícitas: si Routing necesita escalarse algún día, el módulo se extrae con poca cirugía.
- Defendible académicamente: simple sin ser ingenuo.

### Negativas / costo
- Riesgo de que las fronteras se rompan bajo presión de tiempo: un import "atajo" entre módulos puede pasar inadvertido.
- Mitigación: regla en code review + (futuro) `import-linter` con contratos por módulo.

### Neutras
- El módulo `web/` (HTMX + Jinja + Tailwind + Leaflet) vive dentro del mismo proceso que sirve la API. Esto es el patrón normal cuando se sirven templates desde FastAPI; no hay separación frontend/backend. Decisión coherente con ADR-0004.

## Cumplimiento / verificación

- **Estructura de carpetas**: `src/sentinel_dispatch/<modulo>/` con `__init__.py` que define la interfaz pública.
- **Code review**: rechazar PRs que importen entre módulos saltándose la interfaz pública.
- **Futuro**: agregar `import-linter` en CI con contratos declarativos cuando los módulos crezcan más allá del scaffolding.
- **Tests**: `tests/unit/<modulo>/` espejean los módulos. Si un test de un módulo necesita importar de otro, eso es señal de acoplamiento mal puesto.

## Referencias

- [ADR-0001 — Stack](0001-stack.md)
- [Modular Monoliths — Simon Brown (InfoQ)](https://www.infoq.com/presentations/modular-monoliths/)
- *Building Evolutionary Architectures* — Ford, Parsons, Kua (cap. monolitos modulares).
