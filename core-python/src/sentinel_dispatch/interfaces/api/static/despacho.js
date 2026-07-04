/* =============================================================
   Sentinel-Dispatch — Consola de despacho con mapa Leaflet
   Vanilla JS, sin frameworks, sin build step.
   ============================================================= */

(function () {
  'use strict';

  /* Guard: si Leaflet no cargó (CDN caído / sin conexión), avisa en vez
     de fallar en silencio dejando el mapa inerte. */
  if (typeof L === 'undefined') {
    const panel = document.getElementById('panel-despacho');
    if (panel) {
      panel.innerHTML =
        '<span class="placeholder">ERROR: no se pudo cargar Leaflet (¿sin conexión?).</span>';
    }
    return;
  }

  /* -----------------------------------------------------------
     Constantes
     ----------------------------------------------------------- */
  const ENDPOINT            = '/consola/despacho/despachar';
  const ENDPOINT_RED        = '/consola/despacho/red-vial';
  const ENDPOINT_RESET      = '/consola/despacho/reset';
  const ENDPOINT_PENDIENTES = '/consola/despacho/incidentes';
  const BOUNDS_SW = [-30.10, -71.45];
  const BOUNDS_NE = [-29.85, -71.15];
  const COLOR_PHOSPHOR = '#00ff41';
  const COLOR_CRIT     = '#ff003c';
  const COLOR_AMBER    = '#ffb000';
  const SNAP_AVISO_M   = 500;

  /* -----------------------------------------------------------
     Estado de la aplicación
     ----------------------------------------------------------- */
  let latIncidente  = null;
  let lonIncidente  = null;
  let marcadorIncidente = null;
  let marcadorUnidad    = null;
  let polylineRuta      = null;

  /* Balizas del triaje (puente triaje → despacho) */
  let marcadoresPendientes  = {};   // id -> circleMarker
  let incidenteSeleccionado = null; // id de la baliza elegida, o null (clic manual)

  /* -----------------------------------------------------------
     Inicialización del mapa
     ----------------------------------------------------------- */
  const map = L.map('mapa', {
    attributionControl: false,
    zoomControl: true,
  });

  map.fitBounds([BOUNDS_SW, BOUNDS_NE]);

  /* Sin tile layer: fondo negro lo aporta el CSS del contenedor. */

  /* -----------------------------------------------------------
     Wireframe de la red vial — capa de fondo, debajo de ruta y marcadores
     ----------------------------------------------------------- */
  /* Pane dedicado con zIndex bajo el overlayPane (400): el wireframe queda
     siempre detrás de la ruta y los marcadores, sin depender del timing
     del fetch. pointer-events:none evita que intercepte clics del mapa. */
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
          color:       'rgba(0,255,65,0.25)',
          weight:      1,
          opacity:     0.5,
          interactive: false,
        }).addTo(map);
      });
    } catch (_) {
      /* Sin wireframe: la vista continúa operativa */
    }
  })();

  /* -----------------------------------------------------------
     Referencias DOM
     ----------------------------------------------------------- */
  const btnDespachar  = document.getElementById('btn-despachar');
  const btnReset      = document.getElementById('btn-reset');
  const coordDisplay  = document.getElementById('coord-incidente');
  const panelDespacho = document.getElementById('panel-despacho');

  /** Valor del control segmentado de categoría (radios `categoria_mpds`). */
  function categoriaSeleccionada() {
    const marcado = document.querySelector('input[name="categoria_mpds"]:checked');
    return marcado ? marcado.value : 'Charlie';
  }

  /** Marca una categoría en el control segmentado (al elegir una baliza). */
  function marcarCategoria(valor) {
    const radio = document.querySelector(
      `input[name="categoria_mpds"][value="${valor}"]`
    );
    if (radio) { radio.checked = true; }
  }

  /** Coloca (o mueve) el marcador de incidente y habilita el despacho. */
  function ubicarIncidente(lat, lon) {
    latIncidente = lat;
    lonIncidente = lon;
    if (marcadorIncidente) {
      marcadorIncidente.setLatLng([lat, lon]);
    } else {
      marcadorIncidente = L.circleMarker([lat, lon], {
        radius: 8,
        color: COLOR_CRIT,
        fillColor: COLOR_CRIT,
        fillOpacity: 0.9,
        weight: 2,
        className: 'marcador-incidente',
      }).addTo(map);
    }
    btnDespachar.disabled = false;
  }

  /* -----------------------------------------------------------
     Balizas pendientes del triaje: cada clasificación deja un
     incidente en el mapa; clickearlo lo selecciona para despachar.
     ----------------------------------------------------------- */
  async function cargarPendientes() {
    Object.values(marcadoresPendientes).forEach(function (m) { map.removeLayer(m); });
    marcadoresPendientes = {};
    try {
      const res = await fetch(ENDPOINT_PENDIENTES);
      if (!res.ok) return;
      const data = await res.json();
      (data.incidentes || []).forEach(function (inc) {
        const m = L.circleMarker([inc.lat, inc.lon], {
          radius: 9,
          color: COLOR_CRIT,
          fillColor: COLOR_CRIT,
          fillOpacity: 0.3,
          weight: 2,
          className: 'marcador-pendiente',
        }).addTo(map);
        m.bindTooltip(`${inc.id} · ${inc.categoria_mpds}`, { direction: 'top' });
        m.on('click', function (ev) {
          L.DomEvent.stopPropagation(ev); /* que no caiga al clic del mapa */
          seleccionarBaliza(inc);
        });
        marcadoresPendientes[inc.id] = m;
      });
    } catch (_) {
      /* Sin balizas: la vista sigue operativa */
    }
  }

  /** Selecciona una baliza: fija coords + categoría y deja todo listo. */
  function seleccionarBaliza(inc) {
    incidenteSeleccionado = inc.id;
    marcarCategoria(inc.categoria_mpds);
    ubicarIncidente(inc.lat, inc.lon);
    coordDisplay.textContent =
      `${inc.id} — ${inc.lat.toFixed(4)}, ${inc.lon.toFixed(4)}`;
    coordDisplay.classList.add('activo');
  }

  /** Quita la baliza ya despachada del mapa y del estado local. */
  function consumirBaliza(id) {
    const m = marcadoresPendientes[id];
    if (m) { map.removeLayer(m); delete marcadoresPendientes[id]; }
    if (incidenteSeleccionado === id) { incidenteSeleccionado = null; }
  }

  cargarPendientes();

  /* -----------------------------------------------------------
     Helpers
     ----------------------------------------------------------- */

  /**
   * Formatea segundos como "MM:SS".
   * @param {number} seg
   * @returns {string}
   */
  function formatETA(seg) {
    if (seg == null || isNaN(seg)) return '--:--';
    const total = Math.round(seg);
    const mm = String(Math.floor(total / 60)).padStart(2, '0');
    const ss = String(total % 60).padStart(2, '0');
    return `${mm}:${ss}`;
  }

  /**
   * Limpia capas de la respuesta anterior (ruta + marcador de unidad).
   * El marcador de incidente se conserva.
   */
  function limpiarCapasPrevias() {
    if (polylineRuta) { map.removeLayer(polylineRuta); polylineRuta = null; }
    if (marcadorUnidad) { map.removeLayer(marcadorUnidad); marcadorUnidad = null; }
  }

  /**
   * Limpieza total del mapa y del estado: quita ruta, unidad e incidente.
   * El wireframe de fondo no se toca.
   */
  function limpiarTodo() {
    limpiarCapasPrevias();
    if (marcadorIncidente) { map.removeLayer(marcadorIncidente); marcadorIncidente = null; }
    latIncidente = null;
    lonIncidente = null;
  }

  /**
   * Aplica la clase de variante al panel de despacho.
   * @param {'optimo'|'advertencia'|'critico'|''} variante
   */
  function setPanelVariante(variante) {
    panelDespacho.classList.remove(
      'resultado--optimo',
      'resultado--advertencia',
      'resultado--critico'
    );
    if (variante) {
      panelDespacho.classList.add(`resultado--${variante}`);
    }
  }

  /**
   * Renderiza el contenido del panel con los datos del despacho.
   * @param {Object} datos — cuerpo JSON de la respuesta 200.
   */
  function renderizarResultado(datos) {
    const {
      categoria_mpds,
      unidad_seleccionada,
      despacho_suboptimo,
      motivo,
      eta_segundos,
      costo,
      geo,
    } = datos;

    const sinUnidad  = !unidad_seleccionada || motivo === 'saturacion';
    const unidadId   = sinUnidad ? '—' : unidad_seleccionada.id;
    const etaFmt     = formatETA(eta_segundos);
    const snapM      = geo?.snap_m ?? 0;
    const costoTotal = costo?.total ?? null;

    /* Variante de color según resultado */
    let variante = 'optimo';
    if (sinUnidad || motivo === 'saturacion') {
      variante = 'critico';
    } else if (despacho_suboptimo || motivo === 'penalizado' || motivo === 'suboptimo_rn02') {
      variante = 'advertencia';
    }
    setPanelVariante(variante);

    /* Bloque principal */
    let html = `
      <table class="resultado-tabla">
        <tr>
          <td class="campo-label">CATEGORÍA</td>
          <td class="resultado-motivo">${categoria_mpds}</td>
        </tr>
        <tr>
          <td class="campo-label">UNIDAD</td>
          <td class="resultado-valor-grande">${unidadId}</td>
        </tr>
        <tr>
          <td class="campo-label">ETA</td>
          <td class="resultado-valor-grande">${sinUnidad ? '--:--' : etaFmt}</td>
        </tr>
        <tr>
          <td class="campo-label">MOTIVO</td>
          <td class="resultado-motivo">${(motivo || '').toUpperCase()}</td>
        </tr>
    `;

    if (!sinUnidad && costoTotal != null) {
      html += `
        <tr>
          <td class="campo-label">COSTO TOTAL</td>
          <td>${costoTotal.toFixed(1)} s</td>
        </tr>
      `;
    }

    html += `</table>`;

    /* Aviso de sin unidad disponible */
    if (sinUnidad) {
      html += `<p class="resultado-motivo" style="margin-top:0.75rem;">SIN UNIDAD DISPONIBLE</p>`;
    }

    /* Aviso de despacho subóptimo */
    if (!sinUnidad && despacho_suboptimo) {
      html += `<p class="aviso-suboptimo">DESPACHO SUBÓPTIMO — revisar disponibilidad de flota</p>`;
    }

    /* Aviso de snap lejano (RN-09) */
    if (snapM > SNAP_AVISO_M) {
      html += `<p class="aviso-snap">INCIDENTE A ${Math.round(snapM)} m DE LA VÍA MÁS CERCANA — RN-09</p>`;
    }

    panelDespacho.innerHTML = html;
  }

  /**
   * Dibuja la ruta y el marcador de base de unidad sobre el mapa.
   * @param {Object} geo — objeto geo de la respuesta.
   * @param {string|null} etiquetaRuta — trazabilidad "U-XX → I-XXX" o null.
   */
  function dibujarCapasMapa(geo, etiquetaRuta) {
    limpiarCapasPrevias();

    /* Polyline de la ruta A* — la clase CSS anima el flujo de guiones
       en dirección al incidente (despacho.css: .ruta-astar). */
    if (geo.ruta && geo.ruta.length > 1) {
      polylineRuta = L.polyline(geo.ruta, {
        color: COLOR_PHOSPHOR,
        weight: 4,
        opacity: 0.9,
        className: 'ruta-astar',
      }).addTo(map);

      /* Trazabilidad: la ruta declara qué unidad va a qué incidente */
      if (etiquetaRuta) {
        polylineRuta.bindTooltip(etiquetaRuta, { sticky: true });
      }

      map.fitBounds(polylineRuta.getBounds(), { padding: [40, 40] });
    }

    /* Marcador de la base de unidad seleccionada */
    if (geo.unidad_base) {
      marcadorUnidad = L.circleMarker(geo.unidad_base, {
        radius: 7,
        color: COLOR_PHOSPHOR,
        fillColor: COLOR_PHOSPHOR,
        fillOpacity: 0.85,
        weight: 2,
      }).addTo(map);

      /* Etiqueta fija con la unidad despachada, junto a su base */
      if (etiquetaRuta) {
        marcadorUnidad.bindTooltip(etiquetaRuta, {
          permanent: true,
          direction: 'top',
          offset: [0, -8],
        });
      }
    }

    /* Los puntos deben quedar visibles sobre la línea de la ruta */
    if (marcadorIncidente) { marcadorIncidente.bringToFront(); }
    if (marcadorUnidad)    { marcadorUnidad.bringToFront(); }
  }

  /* -----------------------------------------------------------
     Interacción: clic en el mapa — colocar marcador de incidente
     ----------------------------------------------------------- */
  map.on('click', function (e) {
    /* Clic manual: deja de apuntar a una baliza del triaje (si la había) */
    incidenteSeleccionado = null;

    /* Habilitar despacho: recolocar el incidente reabre un despacho
       (un incidente = un despacho hasta que el operador lo mueva). */
    ubicarIncidente(e.latlng.lat, e.latlng.lng);

    coordDisplay.textContent =
      `${e.latlng.lat.toFixed(4)}, ${e.latlng.lng.toFixed(4)}`;
    coordDisplay.classList.add('activo');
  });

  /* -----------------------------------------------------------
     Interacción: botón DESPACHAR
     ----------------------------------------------------------- */
  btnDespachar.addEventListener('click', async function () {
    if (latIncidente == null || lonIncidente == null) return;

    const categoria = categoriaSeleccionada();

    /* Estado de carga */
    btnDespachar.disabled = true;
    btnDespachar.classList.add('cargando');
    panelDespacho.innerHTML = '<span class="placeholder">DESPACHANDO...</span>';
    setPanelVariante('');

    /* Body form-urlencoded */
    const body = new URLSearchParams({
      lat:           latIncidente,
      lon:           lonIncidente,
      categoria_mpds: categoria,
    });
    if (incidenteSeleccionado) {
      body.set('incidente_id', incidenteSeleccionado);
    }

    let respuesta;
    try {
      respuesta = await fetch(ENDPOINT, {
        method:  'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body:    body.toString(),
      });
    } catch (err) {
      /* Error de red: el despacho no se concretó, se puede reintentar */
      setPanelVariante('critico');
      panelDespacho.innerHTML =
        `<span class="resultado-motivo">ERROR DE RED — ${err.message}</span>`;
      btnDespachar.classList.remove('cargando');
      btnDespachar.disabled = false;
      return;
    }

    btnDespachar.classList.remove('cargando');

    /* --- 200 OK -------------------------------------------- */
    if (respuesta.ok) {
      let datos;
      try {
        datos = await respuesta.json();
      } catch (_) {
        setPanelVariante('critico');
        panelDespacho.innerHTML =
          '<span class="resultado-motivo">RESPUESTA INVÁLIDA DEL SERVIDOR</span>';
        btnDespachar.disabled = false;
        return;
      }

      /* Dibujar capas en el mapa (limpia previas), con la etiqueta de
         trazabilidad unidad → incidente cuando hubo despacho efectivo. */
      if (datos.geo) {
        const conUnidad = datos.unidad_seleccionada && datos.motivo !== 'saturacion';
        const etiqueta = conUnidad
          ? `${datos.unidad_seleccionada.id} → ${datos.incidente_id}`
          : null;
        dibujarCapasMapa(datos.geo, etiqueta);
      } else {
        limpiarCapasPrevias();
      }

      /* Renderizar el panel */
      renderizarResultado(datos);

      /* Idempotencia por incidente: si se asignó unidad, el botón queda
         deshabilitado hasta que el operador recoloque el incidente. En
         saturación (sin unidad) se permite reintentar. */
      const huboUnidad = datos.unidad_seleccionada && datos.motivo !== 'saturacion';
      if (huboUnidad && incidenteSeleccionado) {
        consumirBaliza(incidenteSeleccionado);
      }
      btnDespachar.disabled = !!huboUnidad;
      return;
    }

    /* --- 422: fuera de región (detail.mensaje) o validación (detail array) */
    if (respuesta.status === 422) {
      let detalle = 'COORDENADAS FUERA DEL ÁREA DE COBERTURA';
      try {
        const cuerpo = await respuesta.json();
        if (Array.isArray(cuerpo?.detail)) {
          detalle = 'PARÁMETROS INVÁLIDOS';
        } else if (typeof cuerpo?.detail?.mensaje === 'string') {
          detalle = cuerpo.detail.mensaje;
        }
      } catch (_) {
        /* Conserva el fallback fijo */
      }
      limpiarCapasPrevias();
      setPanelVariante('critico');
      panelDespacho.innerHTML =
        `<span class="resultado-motivo">${detalle}</span>`;
      btnDespachar.disabled = false;
      return;
    }

    /* --- Otro error HTTP ------------------------------------ */
    setPanelVariante('critico');
    panelDespacho.innerHTML =
      `<span class="resultado-motivo">ERROR ${respuesta.status} — ${respuesta.statusText}</span>`;
    btnDespachar.disabled = false;
  });

  /* -----------------------------------------------------------
     Interacción: botón REINICIAR FLOTA
     ----------------------------------------------------------- */
  btnReset.addEventListener('click', async function () {
    btnReset.disabled = true;

    try {
      const res = await fetch(ENDPOINT_RESET, { method: 'POST' });
      if (!res.ok) {
        setPanelVariante('advertencia');
        panelDespacho.innerHTML =
          `<span class="resultado-motivo">RESET FALLIDO — ${res.status} ${res.statusText}</span>`;
        btnReset.disabled = false;
        return;
      }
    } catch (err) {
      setPanelVariante('advertencia');
      panelDespacho.innerHTML =
        `<span class="resultado-motivo">ERROR DE RED AL REINICIAR — ${err.message}</span>`;
      btnReset.disabled = false;
      return;
    }

    /* Limpiar estado local y UI; el wireframe de fondo no se toca.
       El servidor ya descartó las balizas pendientes: recargar la capa. */
    limpiarTodo();
    incidenteSeleccionado = null;
    cargarPendientes();
    map.fitBounds([BOUNDS_SW, BOUNDS_NE]);
    setPanelVariante('');
    panelDespacho.innerHTML = '<span class="placeholder">// ESPERANDO DESPACHO</span>';
    coordDisplay.textContent = '// SIN UBICACIÓN';
    coordDisplay.classList.remove('activo');
    btnDespachar.disabled = true;
    btnReset.disabled = false;
  });

})();
