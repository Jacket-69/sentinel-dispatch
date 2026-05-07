---
adr: 0004
title: Frontend retro CRT/phosphor con HTMX + Tailwind + Leaflet
status: accepted
date: 2026-05-06
deciders: Benjamin López
tags: [adr, frontend, ux]
---

# ADR 0004 — Frontend retro CRT/phosphor con HTMX + Tailwind + Leaflet

## Contexto

Sentinel-Dispatch necesita una **consola de despacho web** operada por el "Operador de Despacho" (sec. 2.4 SRS). Las vistas mínimas:

1. Triaje (formulario con árbol MPDS).
2. Despacho con mapa (visualización de unidad propuesta + ETA + ruta A*).
3. Panel de unidades (estado en tiempo real).
4. Alerta de re-despacho (modal con confirmación humana, RN-06).
5. Vista de log (auditoría).

Hay que decidir **stack y estética** del frontend. Hay restricciones reales:

- Equipo de 1–2 personas; cualquier toolchain JS pesado roba tiempo del A*.
- Plazo 2 meses con entregas académicas intermedias.
- Defensa oral: la interfaz debe **diferenciarse visualmente**, no parecer otro CRUD genérico.
- Operador real opera bajo presión: layout claro, jerarquía visual fuerte, sin cognitive overhead.

Benjamin pidió explícitamente una **estética retro arcade tipo Watch Dogs 2 minijuegos / FNAF arcade / Hacknet**: terminal verde sobre negro, scanlines, ASCII art, look "phosphor".

## Decisión

Stack frontend:

- **HTMX** para interactividad sin SPA framework.
- **Tailwind CSS** + CSS custom para la estética CRT.
- **Jinja2** como motor de templates (servido por la misma FastAPI app, ADR-0002).
- **Leaflet** para el mapa con **tiles deshabilitadas** — fondo negro y solo el grafo OSM dibujado como `polyline` verde fina.
- **Sin build step ni toolchain JS**: Tailwind compilado vía `tailwindcss` CLI standalone (binario, sin Node) o CDN durante desarrollo.

Estética: estilo **CRT/phosphor terminal** (a.k.a. "BBS aesthetic", "hacker UI", "retrocomputing").

### Paleta

| Token | Hex | Uso |
|---|---|---|
| `--bg` | `#0a0a0a` | Fondo |
| `--phosphor` | `#00ff41` | Texto primario, líneas del grafo, bordes |
| `--amber` | `#ffb000` | Alertas (EnRuta, advertencias) |
| `--crit` | `#ff003c` | Críticos (Echo/Delta, despacho sub-óptimo) |
| `--panel` | `#1a1a1a` | Paneles, fondos secundarios |
| `--dim` | `#005c20` | Texto secundario |

### Tipografía

- **`VT323`** (Google Fonts) — títulos, labels grandes; pixelada CRT.
- **`JetBrains Mono`** o **`IBM Plex Mono`** — datos, tablas, formularios.
- ALL CAPS en encabezados.

### Efectos CSS canónicos

- **Scanlines**: `linear-gradient` overlay con líneas horizontales sutiles a ~2px.
- **Glow de fósforo**: `text-shadow: 0 0 8px currentColor` en texto importante.
- **Flicker**: animación CSS de `opacity` 99–100% cada 200 ms (sutil, sin marear).
- **Cursor parpadeante** en inputs activos.

### Iconografía

- **Tablas con bordes Unicode**: `╔═╗ ║ ╚╝ ├─┼─┤`.
- **Barras de progreso**: `[████░░░░] 67%`.
- **Iconos de unidades en el mapa**: `▲` (Avanzada), `■` (Básica), color por estado.

### Mapa Leaflet

- **Sin tile layer satelital ni de calles**.
- Fondo negro plano.
- El grafo OSM se dibuja como `polyline` verdes finas (≈1 px) extraídas del `coquimbo.graphml`.
- Las unidades como `divIcon` con caracteres ASCII en color por estado.
- La ruta A* propuesta se dibuja en **ámbar** sobre el grafo.
- Resultado visual: parece un **radar/HUD militar**, no Google Maps.

## Alternativas consideradas

### React / Vue + build separado
- **Pros:**
  - Empleable en CV.
  - Componentes reutilizables a escala.
- **Contras:**
  - Toolchain JS de 200 MB; build step; hot reload roto a veces.
  - 1–2 semanas de setup + curva de aprendizaje que se restan al A*.
  - Sin valor adicional para 5 vistas casi estáticas con interactividad puntual.
- **Por qué se descarta:** overkill medible. Lo confirmé con Benjamin.

### Streamlit / Gradio
- **Pros:** prototipado rapidísimo.
- **Contras:**
  - Mapa interactivo cojo (Streamlit no permite custom Leaflet con divIcons sin hacks).
  - Layout limitado por componentes pre-built; estética CRT imposible sin reinventar todo.
  - No se ve profesional para defensa.
- **Por qué se descarta:** mata la estética y la flexibilidad del mapa.

### Server-side rendering puro sin HTMX (Jinja + form submits clásicos)
- **Pros:** simplicidad máxima.
- **Contras:**
  - Cada acción recarga la página completa.
  - El panel de unidades en tiempo real exige updates parciales.
  - El mapa se reinicializa en cada submit, perdiendo zoom/pan del operador.
- **Por qué se descarta:** UX pobre para una consola operacional.

### Alpine.js en lugar de HTMX
- **Pros:** muy liviano (15 KB), declarativo en HTML.
- **Contras:**
  - Mejor para reactividad dentro de la página, peor para "intercambiar HTML desde el servidor" que es el patrón de HTMX.
  - Requiere endpoints JSON + lógica cliente para componer; HTMX deja los endpoints devolviendo HTML directo.
- **Por qué se descarta:** HTMX calza mejor con FastAPI+Jinja para el patrón de vistas que necesitamos. Alpine podría complementar HTMX si en algún caso puntual se necesita reactividad puramente client-side, pero no es default.

### TUI real (terminal en navegador via xterm.js)
- **Pros:** estética 100% terminal real, escribir comandos.
- **Contras:**
  - Operador real no quiere comandos; quiere botones grandes y feedback visual.
  - Demasiado nicho para defensa; el profesor evaluará usabilidad estándar.
- **Por qué se descarta:** divertido pero no operativo.

## Consecuencias

### Positivas
- **Cero toolchain JS**: el `make dev` levanta todo sin `npm install`.
- **Defensa diferenciada**: la estética CRT/phosphor es memorable y coherente con el dominio (operación bajo presión, urgencias, look "centro de control"). Los profesores lo recordarán.
- **Velocidad de desarrollo**: HTMX permite agregar interactividad incrementalmente; cada vista se puede empezar como Jinja puro y agregar `hx-*` cuando duele.
- **Performance**: render server-side; el grafo OSM se dibuja una vez en JS y se reutiliza.

### Negativas / costo
- **Curva HTMX para Fernando**: si viene de SPAs, la mentalidad cambia. Mitigación: un par de patrones canónicos en `docs/coding-standards.md` cuando se escriba la primera vista.
- **Estética CRT puede sentirse cargada en sesiones largas**: ojos cansados. Mitigación: opción de "modo claro" diferida a opt-in si llega a doler; v1 va full retro.
- **Renderizar el grafo OSM como polylines en cliente puede ser pesado** si se cargan todas las aristas de la IV Región. Mitigación: filtrar por bounding box visible al hacer pan/zoom; pre-simplificar el grafo a la resolución necesaria.
- **Accesibilidad** (WCAG): la paleta verde-sobre-negro no cumple ratios AA en todos los pares. Aceptable para proyecto académico no público; documentado en `docs/security/security.md` como limitación conocida.

### Neutras
- Tailwind se sirve por CDN durante desarrollo, compilado a CSS estático para deploy. No hay etapa de build de JS.
- Los assets (fuentes, JS Leaflet) se sirven vía `StaticFiles` de FastAPI desde `src/sentinel_dispatch/web/static/`.

## Cumplimiento / verificación

- `src/sentinel_dispatch/web/static/css/retro.css` define los tokens y efectos canónicos.
- Code review chequea que las vistas usen los tokens (`var(--phosphor)`, `var(--bg)`, etc.) y no hardcodeen colores.
- Cada vista se acompaña de un screenshot en `docs/product/mockups.md` para defensa.
- En F3 se valida la legibilidad con un usuario externo (Fernando o profesor en consultoría).

## Referencias

- [HTMX essays — "Hypermedia-driven applications"](https://htmx.org/essays/hypermedia-driven-applications/)
- [Tailwind CSS standalone CLI](https://tailwindcss.com/blog/standalone-cli)
- [Leaflet docs — disabling tiles](https://leafletjs.com/reference.html#tilelayer)
- *Hacknet* (referencia visual)
- *Watch Dogs 2* — minijuegos hacking (referencia visual)
- [VT323 font](https://fonts.google.com/specimen/VT323)
- [ADR-0001 — Stack](0001-stack.md)
- [ADR-0002 — Monolito modular](0002-monolito-modular.md)
