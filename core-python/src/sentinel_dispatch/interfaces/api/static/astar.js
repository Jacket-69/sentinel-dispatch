/* =============================================================
   Sentinel-Dispatch — Vista A* didáctica
   Anima el orden real de expansión de la frontera del A* (traza
   del endpoint /consola/astar/trazar) sobre el wireframe OSM.
   Vanilla JS + Leaflet, sin build step.
   ============================================================= */

(function () {
  'use strict';

  if (typeof L === 'undefined') {
    const panel = document.getElementById('panel-astar');
    if (panel) {
      panel.innerHTML =
        '<span class="placeholder">ERROR: no se pudo cargar Leaflet (¿sin conexión?).</span>';
    }
    return;
  }

  /* -----------------------------------------------------------
     Constantes
     ----------------------------------------------------------- */
  const ENDPOINT_TRAZA = '/consola/astar/trazar';
  const ENDPOINT_RED   = '/consola/despacho/red-vial';
  const BOUNDS_SW = [-30.10, -71.45];
  const BOUNDS_NE = [-29.85, -71.15];

  const COLOR_ORIGEN    = '#4e8f3c';   /* verde --ok */
  const COLOR_DESTINO   = '#c0392b';   /* rojo --crit */
  const COLOR_FRONTERA  = '#d98f1f';   /* ámbar --warn: nodos expandidos */
  const COLOR_RUTA      = '#35689f';   /* azul: ruta óptima */

  /* -----------------------------------------------------------
     Estado
     ----------------------------------------------------------- */
  let origen = null;         /* [lat, lon] */
  let destino = null;
  let marcadorOrigen = null;
  let marcadorDestino = null;
  let capaExpansion = null;  /* L.layerGroup con renderer canvas */
  let polylineRuta = null;
  let animacion = null;      /* handle de requestAnimationFrame */
  let trazando = false;

  /* -----------------------------------------------------------
     Mapa + wireframe (mismo esquema que la vista de despacho)
     ----------------------------------------------------------- */
  const map = L.map('mapa', { attributionControl: false, zoomControl: true });
  map.fitBounds([BOUNDS_SW, BOUNDS_NE]);

  map.createPane('wireframe');
  map.getPane('wireframe').style.zIndex = 250;
  map.getPane('wireframe').style.pointerEvents = 'none';

  (async function cargarRedVial() {
    try {
      const res = await fetch(ENDPOINT_RED);
      if (!res.ok) return;
      const data = await res.json();
      if (!Array.isArray(data.calles)) return;
      data.calles.forEach(function (puntos) {
        if (!Array.isArray(puntos) || puntos.length < 2) return;
        L.polyline(puntos, {
          pane:        'wireframe',
          color:       'rgba(107,118,134,0.45)',
          weight:      1,
          opacity:     0.5,
          interactive: false,
        }).addTo(map);
      });
    } catch (_) {
      /* Sin wireframe: la vista continúa operativa */
    }
  })();

  /* Renderer canvas: miles de puntos de frontera sin ahogar el SVG */
  const rendererCanvas = L.canvas({ padding: 0.3 });

  /* -----------------------------------------------------------
     Referencias DOM
     ----------------------------------------------------------- */
  const btnTrazar    = document.getElementById('btn-trazar');
  const btnLimpiar   = document.getElementById('btn-limpiar');
  const coordOrigen  = document.getElementById('coord-origen');
  const coordDestino = document.getElementById('coord-destino');
  const panelAstar   = document.getElementById('panel-astar');

  function nodosPorSegundo() {
    const marcado = document.querySelector('input[name="velocidad_anim"]:checked');
    return marcado ? parseInt(marcado.value, 10) : 240;
  }

  function fmtCoord(par) {
    return par[0].toFixed(4) + ', ' + par[1].toFixed(4);
  }

  function fmtSegundos(s) {
    const min = Math.floor(s / 60);
    const seg = Math.round(s % 60);
    return min + ':' + String(seg).padStart(2, '0') + ' min';
  }

  /* -----------------------------------------------------------
     Selección de origen y destino por clic
     ----------------------------------------------------------- */
  function limpiarResultado() {
    if (animacion) { cancelAnimationFrame(animacion); animacion = null; }
    if (capaExpansion) { map.removeLayer(capaExpansion); capaExpansion = null; }
    if (polylineRuta)  { map.removeLayer(polylineRuta);  polylineRuta = null; }
  }

  function limpiarTodo() {
    limpiarResultado();
    if (marcadorOrigen)  { map.removeLayer(marcadorOrigen);  marcadorOrigen = null; }
    if (marcadorDestino) { map.removeLayer(marcadorDestino); marcadorDestino = null; }
    origen = null;
    destino = null;
    coordOrigen.textContent = 'SIN ORIGEN';
    coordOrigen.classList.remove('activo');
    coordDestino.textContent = 'SIN DESTINO';
    coordDestino.classList.remove('activo');
    btnTrazar.disabled = true;
    panelAstar.classList.remove('resultado--optimo', 'resultado--critico');
    panelAstar.innerHTML =
      '<span class="placeholder">MARCA ORIGEN Y DESTINO EN EL MAPA.</span>';
  }

  map.on('click', function (e) {
    if (trazando) { return; }
    const punto = [e.latlng.lat, e.latlng.lng];

    if (origen == null || destino != null) {
      /* Primer clic (o tercer clic: se reinicia la selección) */
      limpiarTodo();
      origen = punto;
      marcadorOrigen = L.circleMarker(punto, {
        radius: 7, color: COLOR_ORIGEN, fillColor: COLOR_ORIGEN,
        fillOpacity: 0.9, weight: 2,
      }).addTo(map).bindTooltip('ORIGEN', { direction: 'top' });
      coordOrigen.textContent = fmtCoord(punto);
      coordOrigen.classList.add('activo');
    } else {
      destino = punto;
      marcadorDestino = L.circleMarker(punto, {
        radius: 7, color: COLOR_DESTINO, fillColor: COLOR_DESTINO,
        fillOpacity: 0.9, weight: 2, className: 'marcador-incidente',
      }).addTo(map).bindTooltip('DESTINO', { direction: 'top' });
      coordDestino.textContent = fmtCoord(punto);
      coordDestino.classList.add('activo');
      btnTrazar.disabled = false;
    }
  });

  btnLimpiar.addEventListener('click', function () {
    if (trazando) { return; }
    limpiarTodo();
  });

  /* -----------------------------------------------------------
     Animación de la traza
     ----------------------------------------------------------- */
  function animarTraza(datos) {
    limpiarResultado();

    const expansiones = datos.expansiones || [];
    capaExpansion = L.layerGroup().addTo(map);

    let indice = 0;
    let tPrevio = null;
    let acumulado = 0;

    function pintarHasta(n) {
      for (; indice < n && indice < expansiones.length; indice++) {
        L.circleMarker(expansiones[indice], {
          renderer: rendererCanvas,
          radius: 2.5,
          stroke: false,
          fillColor: COLOR_FRONTERA,
          fillOpacity: 0.55,
        }).addTo(capaExpansion);
      }
    }

    function actualizarContador() {
      const celda = document.getElementById('astar-expandidos');
      if (celda) { celda.textContent = indice + ' / ' + expansiones.length; }
    }

    function paso(t) {
      if (tPrevio == null) { tPrevio = t; }
      acumulado += ((t - tPrevio) / 1000) * nodosPorSegundo();
      tPrevio = t;

      pintarHasta(Math.floor(acumulado));
      actualizarContador();

      if (indice < expansiones.length) {
        animacion = requestAnimationFrame(paso);
      } else {
        dibujarRutaFinal(datos);
      }
    }

    animacion = requestAnimationFrame(paso);
  }

  function dibujarRutaFinal(datos) {
    trazando = false;
    btnTrazar.disabled = false;
    if (datos.ruta && datos.ruta.length > 1) {
      polylineRuta = L.polyline(datos.ruta, {
        color: COLOR_RUTA,
        weight: 4,
        opacity: 0.95,
        className: 'ruta-astar',
      }).addTo(map);
    }
    if (marcadorOrigen)  { marcadorOrigen.bringToFront(); }
    if (marcadorDestino) { marcadorDestino.bringToFront(); }

    const fila = document.getElementById('astar-estado');
    if (fila) { fila.textContent = 'RUTA ÓPTIMA ENCONTRADA'; }
  }

  function renderizarPanel(datos) {
    panelAstar.classList.remove('resultado--critico');
    panelAstar.classList.add('resultado--optimo');
    /* h(origen) ≤ ETA real: la desigualdad de admisibilidad, con números */
    panelAstar.innerHTML = `
      <table class="resultado-tabla">
        <tr>
          <td class="campo-label">ESTADO</td>
          <td class="resultado-motivo" id="astar-estado">EXPANDIENDO FRONTERA…</td>
        </tr>
        <tr>
          <td class="campo-label">NODOS EXPANDIDOS</td>
          <td class="resultado-valor-grande" id="astar-expandidos">0 / ${datos.nodos_expandidos}</td>
        </tr>
        <tr>
          <td class="campo-label">ETA (COSTO REAL g)</td>
          <td class="resultado-valor-grande">${fmtSegundos(datos.eta_segundos)}</td>
        </tr>
        <tr>
          <td class="campo-label">h(ORIGEN) — COTA INFERIOR</td>
          <td>${fmtSegundos(datos.h_origen_segundos)} · h ≤ costo real ⇒ heurística admisible ⇒ ruta óptima garantizada</td>
        </tr>
        <tr>
          <td class="campo-label">NODOS EN LA RUTA</td>
          <td>${datos.nodos_ruta}</td>
        </tr>
      </table>
    `;
  }

  /* -----------------------------------------------------------
     Botón TRAZAR
     ----------------------------------------------------------- */
  btnTrazar.addEventListener('click', async function () {
    if (origen == null || destino == null || trazando) { return; }

    trazando = true;
    btnTrazar.disabled = true;
    btnTrazar.classList.add('cargando');
    limpiarResultado();
    panelAstar.classList.remove('resultado--optimo', 'resultado--critico');
    panelAstar.innerHTML = '<span class="placeholder">CALCULANDO TRAZA…</span>';

    const body = new URLSearchParams({
      lat_origen:  origen[0],
      lon_origen:  origen[1],
      lat_destino: destino[0],
      lon_destino: destino[1],
    });

    let respuesta;
    try {
      respuesta = await fetch(ENDPOINT_TRAZA, {
        method:  'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body:    body.toString(),
      });
    } catch (err) {
      trazando = false;
      btnTrazar.classList.remove('cargando');
      btnTrazar.disabled = false;
      panelAstar.classList.add('resultado--critico');
      panelAstar.innerHTML =
        `<span class="resultado-motivo">ERROR DE RED — ${err.message}</span>`;
      return;
    }

    btnTrazar.classList.remove('cargando');

    if (!respuesta.ok) {
      trazando = false;
      btnTrazar.disabled = false;
      let detalle = 'NO SE PUDO TRAZAR LA RUTA';
      try {
        const cuerpo = await respuesta.json();
        if (typeof cuerpo?.detail?.mensaje === 'string') {
          detalle = cuerpo.detail.mensaje;
        }
      } catch (_) { /* fallback fijo */ }
      panelAstar.classList.add('resultado--critico');
      panelAstar.innerHTML = `<span class="resultado-motivo">${detalle}</span>`;
      return;
    }

    const datos = await respuesta.json();
    renderizarPanel(datos);
    animarTraza(datos);
  });

  /* -----------------------------------------------------------
     Modo demo (#demo): ruta de muestra Hospital La Serena →
     CESFAM Tierras Blancas, trazada sola (attract mode).
     ----------------------------------------------------------- */
  if (window.location.hash === '#demo') {
    map.whenReady(function () {
      map.fire('click', { latlng: L.latLng(-29.9077, -71.2535) });
      map.fire('click', { latlng: L.latLng(-29.9622, -71.3198) });
      btnTrazar.click();
    });
  }
})();
