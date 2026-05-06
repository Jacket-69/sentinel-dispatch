# Mockups — Consola de despacho (estética CRT/phosphor)

> **Estado:** placeholder. Wireframes detallados pendientes para entrega Tarea 2026-05-07. Estilo: phosphor terminal verde sobre negro, scanlines, ASCII art (referencia: Hacknet, Watch Dogs 2 minijuegos, FNAF arcade).

## Pantallas

1. **Triaje** — formulario con árbol de preguntas; cursor parpadeante; categoría revelada al final.
2. **Despacho con mapa** — Leaflet sin tiles satelitales (fondo negro), grafo OSM como polylines verdes, ambulancias como `▲` (Avanzada) / `■` (Básica).
3. **Panel de unidades** — tabla con bordes Unicode (`├─┼─┤`), estado por color: verde=Disponible, ámbar=EnRuta, rojo=EnEscena, gris=Taller.
4. **Alerta de re-despacho** — modal centrado con borde doble (`╔═══╗`), beep, opciones [CONFIRMAR] / [RECHAZAR].
5. **Vista de log** — scrollback estilo terminal con timestamps y eventos JSON formateados.

## Paleta

- Fondo: `#0a0a0a`
- Verde fósforo (primario): `#00ff41`
- Ámbar (alertas): `#ffb000`
- Rojo (críticos Echo/Delta): `#ff003c`
- Gris paneles: `#1a1a1a`

## Tipografía

- `VT323` (Google Fonts) para títulos grandes.
- `JetBrains Mono` o `IBM Plex Mono` para datos.

## Efectos CSS

- Scanlines: `linear-gradient` overlay con líneas horizontales sutiles.
- Glow texto: `text-shadow: 0 0 8px currentColor`.
- Flicker sutil: animación de `opacity` de 99–100% cada 200 ms.
- Bordes con `box-shadow` interno verde.

## Wireframes ASCII de referencia (provisional)

```
╔══════════════════════ SENTINEL-DISPATCH ══════════════════════╗
║ ▲ ESTADO: OPERACIONAL    │  USUARIO: operador_01    │  19:42  ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║   [F1] TRIAJE  [F2] FLOTA  [F3] LOG  [F4] SIM  [F5] EXIT      ║
║                                                               ║
║  ──────────────  TRIAJE  ──────────────                        ║
║                                                               ║
║  COORDENADAS                                                  ║
║   LAT [-29.910000_]                                           ║
║   LON [-71.256000_]                                           ║
║                                                               ║
║  ¿CONSCIENTE?      [S] [N]                                    ║
║  ¿RESPIRA?         [S] [N]                                    ║
║  ¿SANGRADO?        [S] [N]                                    ║
║  ¿DOLOR TORÁCICO?  [S] [N]                                    ║
║  GRUPO ETARIO      [PED] [ADULTO] [ANCIANO]                   ║
║                                                               ║
║  > CATEGORÍA: ▒▒▒▒▒▒▒                                         ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
```

(Excalidraw para visuales finales — `mockups.excalidraw` cuando se trabaje el entregable.)
