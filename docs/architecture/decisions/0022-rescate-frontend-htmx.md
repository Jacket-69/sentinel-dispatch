---
adr: 0022
title: Reactivación del frontend (consola de operador) — rescate de ADR-0004
status: accepted
date: 2026-06-03
deciders: Benjamín López
tags: [adr, frontend, ux]
reactiva: 0004
---

# ADR 0022 — Reactivación del frontend (consola de operador) — rescate de ADR-0004

## Contexto

[ADR-0004](0004-frontend-retro-htmx.md) definió el stack y la estética del frontend
(HTMX + Jinja2 + Leaflet + paleta CRT/phosphor) y lo marcó deferred hasta F5, con la
nota explícita: *"se rescata como bonus en F5 si sobra tiempo después de cerrar H1–H5"*.

Hoy (2026-06-03) esa condición se cumple:

- El desarrollo del v1 está **finiquitado**. Toda la validación de ruteo cerró
  (ADR-0016 Ruta A, ADR-0021). RT-02 Python↔Java pasa 12/12.
- En H5 quedan exactamente **dos tareas de cierre obligatorias**: el informe v1.0 y
  el tag `v1.0.0-final`. Esas tareas son **la prioridad de H5 y no quedan
  desplazadas por este ADR**; el frontend es trabajo bonus opcional.
- El deadline del curso es 2026-07-15, lo que da **43 días de holgura** desde hoy —
  la ventana prevista por ADR-0004 para el bonus de F5.
- El frontend figura como **bonus #3** en el roadmap del vault.

El desarrollo incremental empieza ahora, vista por vista, paralelo al cierre
documental de H5, con la restricción de que no bloquea ni retrasa el informe ni el tag.

## Decisión

**Se reactiva el stack y la estética de ADR-0004 tal cual**, sin modificar ninguna
decisión de diseño preexistente. La paleta CRT/phosphor, la tipografía, los efectos CSS
canónicos y el esquema del mapa Leaflet definidos en ADR-0004 quedan vigentes e
inalterados.

Detalles de la reactivación:

**(a) Stack idéntico al de ADR-0004.** HTMX para interactividad sin SPA; Jinja2 como
motor de templates servido por la misma FastAPI app (ADR-0002); Leaflet sin tile layer
satelital, fondo negro, grafo como `polyline` verde fina; sin build step ni toolchain
JS.

**(b) Construcción incremental, vista por vista.** El orden arranca por la
**vista de Triaje** (formulario MPDS), que es el entry point natural y no requiere mapa.
Las cuatro vistas restantes (despacho con mapa, panel de unidades, modal de re-despacho
RN-06, vista de log) vienen en iteraciones siguientes, en el orden que dicte la holgura
disponible.

**(c) CSS CRT propio, sin Tailwind por ahora.** Se crea `crt.css` con los tokens y
efectos canónicos (`--phosphor`, `--bg`, scanlines, glow, flicker). Las fuentes VT323 y
JetBrains Mono y la librería htmx se sirven vía CDN durante desarrollo; el vendorizado
local a `interfaces/api/static/` queda como endurecimiento posterior cuando se
estabilicen las vistas. La integración de Tailwind standalone CLI se difiere hasta que la cantidad de
utilidades lo justifique.

**(d) Alcance de RFs.** El frontend cubre RF-07 (visualización de ruta sobre mapa) y
RF-09 (panel de unidades en tiempo real), además de las vistas de triaje y log.
Ninguno de estos RFs es requisito de v1; todos estaban diferidos por ADR-0004 y este
ADR los reactiva como bonus.

## Alternativas consideradas

### Continuar sin frontend hasta entrega final

- **Pros:** riesgo cero de retrasar H5.
- **Contras:** se desaprovecha la holgura y el bonus previsto en el roadmap; la defensa
  queda con solo CLI y notebook.
- **Por qué se descarta:** la holgura de 43 días existe precisamente para este bonus;
  el desarrollo incremental permite pausarlo en cualquier momento si el informe lo exige.

### Reactivar con Tailwind desde el inicio

- **Pros:** utilidades de layout disponibles de inmediato.
- **Contras:** agrega una dependencia de toolchain (binario Tailwind standalone CLI)
  antes de tener siquiera una vista funcional; prematura optimización.
- **Por qué se descarta:** se prefiere empezar con `crt.css` manual (cero dependencias
  nuevas) y agregar Tailwind cuando la cantidad de utilidades lo justifique. La decisión
  se puede revertir en cualquier iteración sin impacto en las vistas ya escritas.

## Consecuencias

### Positivas

- **Diferenciación visual para la defensa**: la estética CRT/phosphor es memorable y
  coherente con el dominio. ADR-0004 ya argumentó esto en detalle.
- **RFs diferidos avanzan**: RF-07 y RF-09 pasan de backlog a implementación real sin
  tocar el dominio ni los tests existentes.
- **Reutiliza `application/` ya probado**: la capa de casos de uso está estable; el
  frontend solo agrega rutas FastAPI + templates, sin modificar lógica de negocio.
- **Pausable en cualquier iteración**: el modelo incremental garantiza que cada vista
  terminada tiene valor independiente; si el informe exige toda la energía, se pausa
  sin dejar trabajo a medias.

### Negativas / costo

- **Esfuerzo que compite con el informe.** Las vistas se construyen en paralelo, pero
  la prioridad de H5 sigue siendo el informe v1.0 y el tag. Si la estimación de tiempo
  falla, el frontend se pausa antes de que el informe se vea afectado.
- **El grafo de 21 MB / 16 679 nodos exige cuidado en Leaflet.** Renderizar las 42 508
  aristas completas en cliente es prohibitivo. Mitigación obligatoria: enviar al cliente
  solo la ruta A* propuesta más las aristas del bounding box visible; pre-simplificar el
  grafo si el pan/zoom lo requiere. Esto es trabajo adicional en la vista de despacho.
- **Templates y estáticos requieren empaquetado.** Las plantillas y estáticos viven en
  `interfaces/api/templates/` y `interfaces/api/static/`, resueltos vía `__file__`. Si en
  el futuro se distribuye el sistema como paquete Python, habrá que incluirlos en la
  configuración de empaquetado de `pyproject.toml` (hatchling). No es bloqueante para v1
  pero es deuda conocida.

### Relación con el SRS y con RT-02

El frontend **no toca el path operativo de despacho ni el dominio**. Agrega rutas
FastAPI + templates sobre la capa `application/` existente. La paridad dual
Python↔Java (RT-02, 12/12 OK) queda **intacta**: Java no porta templates.

RF-07 y RF-09 del SRS estaban diferidos por ADR-0004; este ADR los reactiva como bonus
opcionales. No son requisitos de v1 y su no implementación no afecta la calificación.

## Cumplimiento / verificación

- La primera iteración entrega la vista de Triaje con un test de humo (`TestClient`
  httpx) que comprueba que el endpoint retorna HTML 200 con el formulario MPDS.
- Cada vista posterior sigue el mismo patrón: endpoint + template + test de humo.
- Las vistas usan los tokens canónicos de ADR-0004 (`var(--phosphor)`, `var(--bg)`,
  etc.); code review rechaza colores hardcodeados.
- El informe v1.0 y el tag `v1.0.0-final` se mantienen como criterio de corte de H5;
  si la entrega se acerca y el informe no está listo, el frontend se pausa.

## Referencias

- [ADR-0004](0004-frontend-retro-htmx.md) — stack y estética reactivados por este ADR.
- [ADR-0002](0002-monolito-modular.md) — FastAPI app que sirve los templates.
- [ADR-0021](0021-cp01c-snap-to-edge-criterio-realista.md) — cierre de validación de
  ruteo que habilita la ventana de holgura.
- SRS sec. 2.4 — "Operador de Despacho" (actor principal de la consola).
- SRS RF-07, RF-09 — RFs diferidos que este ADR reactiva como bonus.
