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
  const ENDPOINT = '/consola/despacho/despachar';
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
     Referencias DOM
     ----------------------------------------------------------- */
  const btnDespachar    = document.getElementById('btn-despachar');
  const coordDisplay    = document.getElementById('coord-incidente');
  const panelDespacho   = document.getElementById('panel-despacho');
  const selectCategoria = document.getElementById('select-categoria');

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
   */
  function dibujarCapasMapa(geo) {
    limpiarCapasPrevias();

    /* Polyline de la ruta A* */
    if (geo.ruta && geo.ruta.length > 1) {
      polylineRuta = L.polyline(geo.ruta, {
        color: COLOR_PHOSPHOR,
        weight: 4,
        opacity: 0.9,
      }).addTo(map);

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
    }
  }

  /* -----------------------------------------------------------
     Interacción: clic en el mapa — colocar marcador de incidente
     ----------------------------------------------------------- */
  map.on('click', function (e) {
    latIncidente = e.latlng.lat;
    lonIncidente = e.latlng.lng;

    const latStr = latIncidente.toFixed(4);
    const lonStr = lonIncidente.toFixed(4);

    /* Actualizar o crear el marcador */
    if (marcadorIncidente) {
      marcadorIncidente.setLatLng(e.latlng);
    } else {
      marcadorIncidente = L.circleMarker(e.latlng, {
        radius: 8,
        color: COLOR_CRIT,
        fillColor: COLOR_CRIT,
        fillOpacity: 0.9,
        weight: 2,
      }).addTo(map);
    }

    /* Actualizar display de coordenadas */
    coordDisplay.textContent = `${latStr}, ${lonStr}`;
    coordDisplay.classList.add('activo');

    /* Habilitar botón de despacho */
    btnDespachar.disabled = false;
  });

  /* -----------------------------------------------------------
     Interacción: botón DESPACHAR
     ----------------------------------------------------------- */
  btnDespachar.addEventListener('click', async function () {
    if (latIncidente == null || lonIncidente == null) return;

    const categoria = selectCategoria.value;

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

    let respuesta;
    try {
      respuesta = await fetch(ENDPOINT, {
        method:  'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body:    body.toString(),
      });
    } catch (err) {
      /* Error de red */
      setPanelVariante('critico');
      panelDespacho.innerHTML =
        `<span class="resultado-motivo">ERROR DE RED — ${err.message}</span>`;
      btnDespachar.classList.remove('cargando');
      btnDespachar.disabled = false;
      return;
    }

    btnDespachar.classList.remove('cargando');
    btnDespachar.disabled = false;

    /* --- 200 OK -------------------------------------------- */
    if (respuesta.ok) {
      let datos;
      try {
        datos = await respuesta.json();
      } catch (_) {
        setPanelVariante('critico');
        panelDespacho.innerHTML =
          '<span class="resultado-motivo">RESPUESTA INVÁLIDA DEL SERVIDOR</span>';
        return;
      }

      /* Dibujar capas en el mapa (limpia previas) */
      if (datos.geo) {
        dibujarCapasMapa(datos.geo);
      } else {
        limpiarCapasPrevias();
      }

      /* Renderizar el panel */
      renderizarResultado(datos);
      return;
    }

    /* --- 422 Coordenadas fuera de región ------------------- */
    if (respuesta.status === 422) {
      let detalle;
      try {
        const cuerpo = await respuesta.json();
        detalle = cuerpo?.detail?.mensaje ?? JSON.stringify(cuerpo.detail);
      } catch (_) {
        detalle = 'COORDENADAS FUERA DEL ÁREA DE COBERTURA';
      }
      limpiarCapasPrevias();
      setPanelVariante('critico');
      panelDespacho.innerHTML =
        `<span class="resultado-motivo">${detalle}</span>`;
      return;
    }

    /* --- Otro error HTTP ------------------------------------ */
    setPanelVariante('critico');
    panelDespacho.innerHTML =
      `<span class="resultado-motivo">ERROR ${respuesta.status} — ${respuesta.statusText}</span>`;
  });

})();
