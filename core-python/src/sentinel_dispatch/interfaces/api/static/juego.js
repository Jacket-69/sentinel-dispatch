/* =============================================================
   Sentinel-Dispatch — Minijuego "ambulancia al destino"
   Runner estilo arcade: la ambulancia esquiva obstáculos camino
   al incidente. Canvas pixelart, vanilla JS, sin dependencias.
   Bonus de ocio declarado: sin valor de evaluación (vault 2026-06).
   ============================================================= */

(function () {
  'use strict';

  const canvas = document.getElementById('juego-canvas');
  if (!canvas) { return; }
  const ctx = canvas.getContext('2d');

  /* -----------------------------------------------------------
     Constantes del mundo
     ----------------------------------------------------------- */
  const ANCHO  = canvas.width;    /* 800 */
  const ALTO   = canvas.height;   /* 240 */
  const SUELO_Y = 200;            /* línea de suelo (px) */

  const GRAVEDAD          = 2600;  /* px/s² */
  const IMPULSO_SALTO     = -820;  /* px/s */
  const VELOCIDAD_INICIAL = 320;   /* px/s */
  const VELOCIDAD_MAX     = 780;
  const ACELERACION       = 9;     /* px/s por segundo de juego */

  const CLAVE_RECORD = 'sentinel-juego-record';

  /* Paleta del tema retro (retro.css) */
  const COLORES = {
    cielo:    '#eceef2',
    calle:    '#9aa3b0',
    linea:    '#eceef2',
    texto:    '#24303c',
    tenue:    '#6b7686',
    rojo:     '#c0392b',
    ambar:    '#d98f1f',
    azul:     '#35689f',
    montana:  '#cdd2d9',
  };

  /* -----------------------------------------------------------
     Sprites pixelart — matrices de caracteres, un color por letra.
     '.' es transparente. Se dibujan escalados (PIXEL px por celda).
     ----------------------------------------------------------- */
  const PIXEL = 4;

  const PALETA = {
    W: '#f6f8fa',   /* carrocería */
    R: '#c0392b',   /* cruz + franja */
    B: '#7ba7d4',   /* vidrios */
    D: '#24303c',   /* contorno y ruedas */
    G: '#9aa3b0',   /* parachoques */
    A: '#d98f1f',   /* baliza ámbar */
    Z: '#35689f',   /* baliza azul */
    N: '#f0a13c',   /* cono: franja */
  };

  /* Ambulancia mirando a la derecha: caja atrás, cabina adelante. */
  const SPRITE_AMBULANCIA = [
    '...........ZA...............',
    '..DDDDDDDDDDDDDDDDDD........',
    '.DWWWWWWWWWWWWWWWWWWD.......',
    '.DWWWRWWWWWWWWWWWWWWDDDDD...',
    '.DWWRRRWWWWWWWWWWWWWDBBBWD..',
    '.DWWWRWWWWWWWWWWWWWWDBBBWD..',
    '.DWWWWWWWWWWWWWWWWWWDWWWWWD.',
    '.DRRRRRRRRRRRRRRRRRRRRRRRRD.',
    '.DWWWWWWWWWWWWWWWWWWWWWWWWD.',
    '.DGGGGGGGGGGGGGGGGGGGGGGGGD.',
    '.DDDDDDDDDDDDDDDDDDDDDDDDDD.',
    '....DDD.............DDD.....',
  ];

  /* Cono de tráfico (obstáculo bajo) */
  const SPRITE_CONO = [
    '....DD....',
    '....NN....',
    '...NNNN...',
    '...NWWN...',
    '..NNNNNN..',
    '..NWWWWN..',
    '.NNNNNNNN.',
    'DDDDDDDDDD',
  ];

  /* Barrera de obras (obstáculo alto) */
  const SPRITE_BARRERA = [
    'DDDDDDDDDDDDDD',
    'DNWWNNWWNNWWND',
    'DWNNWWNNWWNNWD',
    'DDDDDDDDDDDDDD',
    '...DD....DD...',
    '...DD....DD...',
    '...DD....DD...',
    'DDDDDDDDDDDDDD',
  ];

  /** Renderiza una matriz de sprite a un canvas offscreen (una sola vez). */
  function hornearSprite(matriz) {
    const alto = matriz.length;
    const ancho = matriz[0].length;
    const off = document.createElement('canvas');
    off.width = ancho * PIXEL;
    off.height = alto * PIXEL;
    const octx = off.getContext('2d');
    for (let y = 0; y < alto; y++) {
      for (let x = 0; x < ancho; x++) {
        const color = PALETA[matriz[y][x]];
        if (!color) { continue; }
        octx.fillStyle = color;
        octx.fillRect(x * PIXEL, y * PIXEL, PIXEL, PIXEL);
      }
    }
    return off;
  }

  const IMG_AMBULANCIA = hornearSprite(SPRITE_AMBULANCIA);
  const IMG_CONO       = hornearSprite(SPRITE_CONO);
  const IMG_BARRERA    = hornearSprite(SPRITE_BARRERA);

  /* Tipos de obstáculo: sprite + probabilidad relativa */
  const TIPOS_OBSTACULO = [
    { img: IMG_CONO,    peso: 5 },
    { img: IMG_BARRERA, peso: 3 },
  ];

  /* -----------------------------------------------------------
     Estado del juego
     ----------------------------------------------------------- */
  const ESPERANDO = 0, CORRIENDO = 1, CHOCADO = 2;

  let estado, velocidad, distancia, obstaculos, proximoObstaculoEn;
  let ambY, ambVy, enSuelo;
  let tPrevio = null;
  let parpadeo = 0;   /* acumulador para la baliza y las ruedas */

  let record = 0;
  try {
    record = parseInt(localStorage.getItem(CLAVE_RECORD), 10) || 0;
  } catch (_) { /* localStorage bloqueado: se juega sin récord */ }

  const elRecord = document.getElementById('juego-record');
  if (elRecord) { elRecord.textContent = String(record); }

  const AMB_X = 60;
  const AMB_ANCHO = IMG_AMBULANCIA.width;
  const AMB_ALTO  = IMG_AMBULANCIA.height;

  function reiniciar() {
    estado = CORRIENDO;
    velocidad = VELOCIDAD_INICIAL;
    distancia = 0;
    obstaculos = [];
    proximoObstaculoEn = ANCHO + 200;
    ambY = SUELO_Y - AMB_ALTO;
    ambVy = 0;
    enSuelo = true;
  }

  function saltar() {
    if (estado === ESPERANDO) { reiniciar(); return; }
    if (estado === CHOCADO)   { reiniciar(); return; }
    if (enSuelo) {
      ambVy = IMPULSO_SALTO;
      enSuelo = false;
    }
  }

  /* -----------------------------------------------------------
     Obstáculos
     ----------------------------------------------------------- */
  function elegirTipo() {
    const total = TIPOS_OBSTACULO.reduce((s, t) => s + t.peso, 0);
    let r = Math.random() * total;
    for (const t of TIPOS_OBSTACULO) {
      r -= t.peso;
      if (r <= 0) { return t; }
    }
    return TIPOS_OBSTACULO[0];
  }

  function generarObstaculo() {
    const tipo = elegirTipo();
    obstaculos.push({
      x: ANCHO + 20,
      y: SUELO_Y - tipo.img.height,
      img: tipo.img,
    });
    /* Separación aleatoria, más apretada a mayor velocidad */
    const base = 380 + Math.random() * 420;
    proximoObstaculoEn = base * (velocidad / VELOCIDAD_INICIAL) * 0.75;
  }

  /** Colisión AABB con un margen de gracia para ser amable con el jugador. */
  function colisiona(o) {
    const margen = 6;
    return (
      AMB_X + margen < o.x + o.img.width - margen &&
      AMB_X + AMB_ANCHO - margen > o.x + margen &&
      ambY + margen < o.y + o.img.height &&
      ambY + AMB_ALTO - margen > o.y + margen
    );
  }

  /* -----------------------------------------------------------
     Actualización por frame
     ----------------------------------------------------------- */
  function actualizar(dt) {
    if (estado !== CORRIENDO) { return; }

    velocidad = Math.min(VELOCIDAD_MAX, velocidad + ACELERACION * dt);
    distancia += velocidad * dt;

    /* Física del salto */
    ambVy += GRAVEDAD * dt;
    ambY += ambVy * dt;
    if (ambY >= SUELO_Y - AMB_ALTO) {
      ambY = SUELO_Y - AMB_ALTO;
      ambVy = 0;
      enSuelo = true;
    }

    /* Obstáculos: avanzan hacia la ambulancia */
    const dx = velocidad * dt;
    obstaculos.forEach(function (o) { o.x -= dx; });
    obstaculos = obstaculos.filter(function (o) { return o.x + o.img.width > -20; });

    proximoObstaculoEn -= dx;
    if (proximoObstaculoEn <= 0) { generarObstaculo(); }

    for (const o of obstaculos) {
      if (colisiona(o)) {
        estado = CHOCADO;
        const metros = Math.floor(distancia / 10);
        if (metros > record) {
          record = metros;
          if (elRecord) { elRecord.textContent = String(record); }
          try { localStorage.setItem(CLAVE_RECORD, String(record)); } catch (_) { /* sin récord */ }
        }
        break;
      }
    }
  }

  /* -----------------------------------------------------------
     Dibujo
     ----------------------------------------------------------- */
  function dibujarFondo() {
    ctx.fillStyle = COLORES.cielo;
    ctx.fillRect(0, 0, ANCHO, ALTO);

    /* Silueta de cerros de la IV Región, desplazamiento en parallax */
    ctx.fillStyle = COLORES.montana;
    const off = (distancia * 0.15) % 400;
    for (let x = -off; x < ANCHO + 400; x += 400) {
      ctx.beginPath();
      ctx.moveTo(x, SUELO_Y - 40);
      ctx.lineTo(x + 120, SUELO_Y - 110);
      ctx.lineTo(x + 260, SUELO_Y - 55);
      ctx.lineTo(x + 400, SUELO_Y - 40);
      ctx.closePath();
      ctx.fill();
    }

    /* Calle */
    ctx.fillStyle = COLORES.calle;
    ctx.fillRect(0, SUELO_Y - 4, ANCHO, ALTO - SUELO_Y + 4);

    /* Demarcación central discontinua, en movimiento */
    ctx.fillStyle = COLORES.linea;
    const offLinea = (distancia) % 60;
    for (let x = -offLinea; x < ANCHO; x += 60) {
      ctx.fillRect(x, SUELO_Y + 14, 30, 4);
    }
  }

  function dibujarAmbulancia() {
    ctx.drawImage(IMG_AMBULANCIA, AMB_X, Math.round(ambY));

    /* Baliza destellando: alterna azul/ámbar sobre la cabina */
    if (estado === CORRIENDO) {
      const fase = Math.floor(parpadeo * 6) % 2;
      ctx.fillStyle = fase ? PALETA.Z : PALETA.A;
      ctx.fillRect(AMB_X + 11 * PIXEL, Math.round(ambY), 2 * PIXEL, PIXEL);
    }

    /* Ruedas: dos círculos con hub que alterna (sensación de giro),
       centradas en los huecos de rueda del sprite (cols ~5.5 y ~22). */
    const faseRueda = Math.floor(parpadeo * 10) % 2;
    const yRueda = Math.round(ambY) + AMB_ALTO + Math.round(PIXEL * 0.5);
    const radio = Math.round(PIXEL * 2.2);
    [AMB_X + 5.5 * PIXEL, AMB_X + 22 * PIXEL].forEach(function (cx) {
      ctx.fillStyle = PALETA.D;
      ctx.beginPath();
      ctx.arc(cx, yRueda, radio, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = faseRueda ? COLORES.calle : '#e9ebef';
      ctx.fillRect(cx - PIXEL / 2, yRueda - PIXEL / 2, PIXEL, PIXEL);
    });
  }

  function dibujarHUD() {
    ctx.fillStyle = COLORES.texto;
    ctx.font = 'bold 16px "Trebuchet MS", Tahoma, Verdana, sans-serif';
    ctx.textAlign = 'right';
    ctx.fillText(Math.floor(distancia / 10) + ' m', ANCHO - 14, 26);

    ctx.textAlign = 'center';
    if (estado === ESPERANDO) {
      ctx.fillStyle = COLORES.tenue;
      ctx.fillText('ESPACIO / CLIC PARA SALIR A RUTA', ANCHO / 2, 100);
    } else if (estado === CHOCADO) {
      ctx.fillStyle = COLORES.rojo;
      ctx.font = 'bold 22px "Trebuchet MS", Tahoma, Verdana, sans-serif';
      ctx.fillText('COLISIÓN — EL INCIDENTE SIGUE EN ESPERA', ANCHO / 2, 92);
      ctx.fillStyle = COLORES.tenue;
      ctx.font = 'bold 14px "Trebuchet MS", Tahoma, Verdana, sans-serif';
      ctx.fillText('ESPACIO / CLIC PARA REINTENTAR', ANCHO / 2, 118);
    }
  }

  function dibujar() {
    dibujarFondo();
    obstaculos.forEach(function (o) {
      ctx.drawImage(o.img, Math.round(o.x), o.y);
    });
    dibujarAmbulancia();
    dibujarHUD();
  }

  /* -----------------------------------------------------------
     Bucle principal
     ----------------------------------------------------------- */
  function frame(t) {
    if (tPrevio == null) { tPrevio = t; }
    /* dt acotado: al volver de una pestaña en background no "teletransporta" */
    const dt = Math.min((t - tPrevio) / 1000, 0.05);
    tPrevio = t;
    parpadeo += dt;

    actualizar(dt);
    dibujar();
    requestAnimationFrame(frame);
  }

  /* -----------------------------------------------------------
     Entrada: teclado, clic y touch
     ----------------------------------------------------------- */
  document.addEventListener('keydown', function (e) {
    if (e.code === 'Space' || e.code === 'ArrowUp') {
      e.preventDefault();
      saltar();
    }
  });

  canvas.addEventListener('pointerdown', function (e) {
    e.preventDefault();
    saltar();
  });

  /* Arranque: pantalla de espera con la ambulancia en posición.
     Con #demo en la URL parte solo (attract mode / verificación). */
  estado = ESPERANDO;
  velocidad = 0;
  distancia = 0;
  obstaculos = [];
  ambY = SUELO_Y - AMB_ALTO;
  ambVy = 0;
  enSuelo = true;
  if (window.location.hash === '#demo') { reiniciar(); }
  requestAnimationFrame(frame);
})();
