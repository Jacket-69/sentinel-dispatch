---
adr: 0023
title: Estética retro Web 2.0 (~2010) para la consola de operador
status: accepted
date: 2026-07-04
deciders: Benjamín López
tags: [adr, frontend, ux]
supersede-parcial: 0004
---

# ADR 0023 — Estética retro Web 2.0 (~2010) para la consola de operador

## Contexto

[ADR-0004](0004-frontend-retro-htmx.md) (reactivado por
[ADR-0022](0022-reactivacion-frontend-consola.md)) fijó dos cosas distintas en una
misma decisión: el **stack** del frontend (HTMX + Jinja2 + Leaflet, sin build step)
y la **identidad visual** (paleta CRT/phosphor: fondo negro, verde fósforo, scanlines,
glow). La consola se construyó y desplegó con esa estética.

De cara a la presentación final (2026-07), se decidió cambiar la identidad visual a
un tema **retro Web 2.0 (~2010)**: fondo claro con rayas diagonales sutiles, paneles
biselados, gradientes verticales glossy, texto blanco con sombra letterpress sobre
superficies de color, tipografías de sistema de la época (Trebuchet MS / Tahoma /
Verdana) y pills con esquinas redondeadas. Es el mismo lenguaje visual ya usado en
otros proyectos personales del equipo, y elimina además la dependencia de webfonts
de Google (la consola queda 100 % autocontenida salvo HTMX y Leaflet).

## Decisión

- La identidad visual de la consola pasa a ser **retro Web 2.0**, definida en
  `interfaces/api/static/retro.css` (reemplaza a `crt.css`, que se elimina).
- **El stack de ADR-0004/0022 no cambia**: HTMX + Jinja2 + Leaflet, CSS puro a mano,
  sin build step, sin framework CSS. Este ADR supersede solo la porción estética.
- Tokens del tema en `:root` de `retro.css`: superficies (`--bg`, `--panel`,
  `--card-*`), texto (`--text`, `--muted`), marca (`--header-top/bottom`) y
  semánticos con su tope glossy (`--crit`, `--warn`, `--ok`, `--info` + `*-top`).
- La firma visual se encapsula en tokens compartidos: `--bevel`, `--bevel-card`,
  `--bevel-boton` (brillo `inset` superior + sombra proyectada), `--hundido`
  (estado presionado) y `--letterpress`.
- Mapeo semántico de la paleta CRT saliente: phosphor → `--ok` (verde),
  amber → `--warn` (ámbar), crit → `--crit` (rojo), dim → `--muted` (gris).
  Los **nombres de clase** que viajan en fragmentos HTMX
  (`resultado--phosphor/amber/crit/dim`) se conservan como API de severidad para
  no tocar el contrato template ↔ backend.
- El mapa Leaflet pasa a fondo claro: wireframe gris azulado, ruta A* azul
  (`#35689f`), incidentes rojos, unidad verde.

## Alternativas consideradas

- **Mantener CRT/phosphor**: descartada por preferencia declarada del equipo para la
  presentación final; el tema oscuro además rendía peor en proyectores.
- **Tema nuevo con framework CSS (Bootstrap 2 auténtico de la época)**: descartado;
  viola la regla sin-dependencias-pesadas y el espíritu de CSS propio de ADR-0004.

## Consecuencias

- Positivas: legibilidad en proyector, sin webfonts (menos puntos de falla en la
  demo), lenguaje visual consistente con los tableros del equipo, tokens semánticos
  más expresivos que los nombres de color CRT.
- Negativas: los nombres `resultado--phosphor` y afines ya no describen su color
  real (deuda cosmética aceptada para no romper el contrato de fragmentos).
- El CSS por vista (`triaje.css`, `despacho.css`, `unidades.css`, `log.css`,
  `validacion.css`) se reescribió sobre los nuevos tokens; la estructura HTML y las
  clases se mantienen.
