"""Router web de la consola de operador (ADR-0022, rescate de ADR-0004).

Sirve la consola HTMX con estética CRT servida por la misma FastAPI app
(ADR-0002). Primera vista: Triaje (formulario MPDS-subset). Las plantillas
Jinja2 y los estáticos viven junto a este módulo (``templates/`` y
``static/``); el path se resuelve relativo a ``__file__`` para que funcione
tanto en ejecución desde fuente como instalado.

El flujo es hipermedia puro: el ``<form>`` envía un POST por HTMX y el
endpoint devuelve un fragmento HTML (``_resultado_triaje.html``) que se
inyecta en ``#panel-resultado`` sin recargar la página.
"""

from __future__ import annotations

import json
import logging
import os
import random
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from sentinel_dispatch.adapters.grafo_osmnx import OsmnxGrafoVial, cargar_grafo_iv_region
from sentinel_dispatch.adapters.repositorio_jsonl import JsonlRepositorioEventos
from sentinel_dispatch.application.despachar_ambulancia import despachar
from sentinel_dispatch.application.serializacion import serializar_resultado_despacho
from sentinel_dispatch.domain.dispatch.tipos import (
    EstadoUnidad,
    Incidente,
    TipoUnidad,
    Unidad,
)
from sentinel_dispatch.domain.routing.tipos import NodoFueraDeRangoError
from sentinel_dispatch.domain.triaje import (
    CategoriaMPDS,
    GrupoEtario,
    NivelDolorToracico,
    NivelSangrado,
    RespuestaTriaje,
    clasificar_mpds,
)
from sentinel_dispatch.interfaces.api.validacion import (
    FECHA_FIXTURES,
    ResultadoValidacion,
    comparar_validacion_dual,
)
from sentinel_dispatch.ports.repositorio_eventos import (
    EventoDuplicadoError,
    EventoLog,
    TipoEvento,
)

if TYPE_CHECKING:
    from sentinel_dispatch.domain.routing.grafo_vial import GrafoVial

_DIR_BASE = Path(__file__).parent
DIRECTORIO_PLANTILLAS = _DIR_BASE / "templates"
DIRECTORIO_ESTATICOS = _DIR_BASE / "static"

plantillas = Jinja2Templates(directory=str(DIRECTORIO_PLANTILLAS))

# Vistas que la nav de la consola ofrece. El default (presentación 2026-06)
# muestra solo triaje + unidades; la consola completa se reactiva con
# ``SENTINEL_VISTAS=triaje,despacho,unidades,log`` (o cualquier subconjunto).
# Controla solo la navegación: las rutas siguen registradas y accesibles por
# URL directa (deep links y tests no cambian), y la vista activa siempre
# aparece en la nav aunque no esté habilitada.
_VISTAS_TODAS = ("triaje", "despacho", "unidades", "log", "validacion")
_VISTAS_DEFAULT = ("triaje", "unidades")


def vistas_habilitadas() -> tuple[str, ...]:
    """Vistas visibles en la nav, desde env ``SENTINEL_VISTAS`` o el default.

    Se evalúa en cada render (es un global Jinja invocable), así los tests
    pueden variar el env sin reimportar el módulo. Valores desconocidos en el
    CSV se ignoran; un CSV sin valores válidos cae al default.
    """
    env = os.environ.get("SENTINEL_VISTAS")
    if not env:
        return _VISTAS_DEFAULT
    habilitadas = tuple(v for v in (s.strip() for s in env.split(",")) if v in _VISTAS_TODAS)
    return habilitadas or _VISTAS_DEFAULT


plantillas.env.globals["vistas_habilitadas"] = vistas_habilitadas

# Cache-busting de los estáticos: las plantillas anexan ?v=<versión> a cada
# <link>/<script> de /static. Bump manual al cambiar CSS/JS — sin esto, los
# navegadores que visitaron la consola siguen sirviendo la hoja vieja cacheada.
VERSION_ESTATICOS = "20260704-1"
plantillas.env.globals["version_estaticos"] = VERSION_ESTATICOS

router = APIRouter(tags=["consola"])

_log = logging.getLogger(__name__)


def _ahora_iso_z() -> str:
    """Timestamp UTC ISO 8601 con sufijo ``Z`` (formato congelado en ADR-0018)."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


# Presentación por categoría: token de severidad CSS + descripción breve para
# el operador. Las descripciones replican la semántica MPDS documentada en
# domain/triaje/tipos.py; el token alimenta la clase .resultado--<severidad>
# del fragmento (crt.css define crit / amber / phosphor / dim).
_PRESENTACION: dict[CategoriaMPDS, tuple[str, str]] = {
    CategoriaMPDS.ECHO: ("crit", "ALS + recursos múltiples — paro inminente."),
    CategoriaMPDS.DELTA: ("crit", "ALS urgente (Avanzada, con sirena)."),
    CategoriaMPDS.CHARLIE: ("amber", "ALS no urgente (Avanzada, sin sirena)."),
    CategoriaMPDS.BRAVO: ("phosphor", "BLS urgente (Básica, con sirena)."),
    CategoriaMPDS.ALPHA: ("dim", "BLS no urgente (Básica, sin sirena)."),
}


@router.get("/", include_in_schema=False)
async def raiz() -> RedirectResponse:
    """Redirige la raíz a la consola de triaje (entry point del operador)."""
    return RedirectResponse(url="/consola/triaje")


@router.get("/consola/triaje", response_class=HTMLResponse)
async def vista_triaje(request: Request) -> HTMLResponse:
    """Renderiza el formulario de triaje de la consola CRT."""
    return plantillas.TemplateResponse(
        request=request, name="triaje.html", context={"vista_activa": "triaje"}
    )


# Bbox urbano de la conurbación La Serena-Coquimbo para generar incidentes
# de demo: (lat_min, lat_max, lon_min, lon_max). Más apretado que el bbox de
# cobertura del grafo, así las balizas caen en la trama urbana.
_BBOX_URBANO = (-29.98, -29.88, -71.34, -71.22)


def obtener_incidentes_pendientes(request: Request) -> dict[str, dict[str, Any]]:
    """Dependencia: incidentes generados desde el triaje, pendientes de despacho.

    Overlay en memoria (mismo patrón que :func:`obtener_estados_unidades`):
    cada clasificación de triaje agrega una baliza que la vista de despacho
    pinta en el mapa; despacharla la consume. No persiste (v1, ADR-0022).
    """
    pendientes = getattr(request.app.state, "incidentes_pendientes", None)
    if pendientes is None:
        pendientes = {}
        request.app.state.incidentes_pendientes = pendientes
    return cast("dict[str, dict[str, Any]]", pendientes)


def _coordenadas_incidente_aleatorio(grafo: GrafoVial | None) -> tuple[float, float]:
    """Punto aleatorio de la conurbación, snapeado a la red vial si hay grafo.

    Sin grafo (tests con ASGITransport, server aún cargándolo) se usa el punto
    crudo del bbox: suficiente para pintar la baliza; el despacho posterior
    snapea de todas formas.
    """
    # S311: random no criptográfico — correcto acá, es ubicación de demo.
    lat = random.uniform(_BBOX_URBANO[0], _BBOX_URBANO[1])  # noqa: S311
    lon = random.uniform(_BBOX_URBANO[2], _BBOX_URBANO[3])  # noqa: S311
    if grafo is not None:
        try:
            nodo = grafo.nodo_mas_cercano(lat, lon)
            return grafo.coordenadas(nodo)
        except NodoFueraDeRangoError:
            pass
    return (lat, lon)


@router.post("/consola/triaje/clasificar", response_class=HTMLResponse)
async def clasificar_triaje(
    request: Request,
    consciente: bool = Form(...),
    respira_normal: bool = Form(...),
    sangrado: NivelSangrado = Form(...),
    dolor_toracico: NivelDolorToracico = Form(...),
    dificultad_respiratoria: bool = Form(...),
    grupo_etario: GrupoEtario = Form(...),
    pendientes: dict[str, dict[str, Any]] = Depends(obtener_incidentes_pendientes),
) -> HTMLResponse:
    """Clasifica una respuesta de triaje y devuelve el fragmento de resultado.

    Construye la :class:`RespuestaTriaje` desde el formulario, delega en el
    dominio (:func:`clasificar_mpds`) y renderiza el fragmento HTMX. Un valor
    fuera de los enums lo rechaza FastAPI con 422 antes de llegar al dominio.
    """
    respuesta = RespuestaTriaje(
        consciente=consciente,
        respira_normal=respira_normal,
        sangrado=sangrado,
        dolor_toracico=dolor_toracico,
        dificultad_respiratoria=dificultad_respiratoria,
        grupo_etario=grupo_etario,
    )
    categoria = clasificar_mpds(respuesta)
    severidad, descripcion = _PRESENTACION[categoria]

    # Puente triaje → despacho: cada clasificación genera un incidente de demo
    # en un punto aleatorio de la conurbación; queda como baliza en el mapa
    # hasta que el operador lo despache (o reinicie la consola).
    lat, lon = _coordenadas_incidente_aleatorio(getattr(request.app.state, "grafo", None))
    secuencia = getattr(request.app.state, "seq_incidentes", 0) + 1
    request.app.state.seq_incidentes = secuencia
    incidente_id = f"I-TRIAJE-{secuencia:03d}"
    pendientes[incidente_id] = {
        "id": incidente_id,
        "lat": round(lat, 6),
        "lon": round(lon, 6),
        "categoria_mpds": categoria.value,
        "timestamp_iso": _ahora_iso_z(),
    }

    return plantillas.TemplateResponse(
        request=request,
        name="_resultado_triaje.html",
        context={
            "categoria": categoria.value,
            "severidad": severidad,
            "descripcion": descripcion,
            "incidente_id": incidente_id,
        },
    )


# ---------------------------------------------------------------------------
# Panel de unidades (RF-09) y vista de log (RF-06) — ADR-0022
# ---------------------------------------------------------------------------

_MONOREPO_ROOT = Path(__file__).resolve().parents[5]
_UNIDADES_PATH = _MONOREPO_ROOT / "data" / "dataset" / "unidades.json"
_LOG_EVENTOS_DEFAULT = _MONOREPO_ROOT / "data" / "_runtime" / "eventos.jsonl"

# Estado de la unidad -> token de color CSS (clase fila--<token> en la plantilla).
_TOKEN_ESTADO: dict[EstadoUnidad, str] = {
    EstadoUnidad.DISPONIBLE: "disponible",
    EstadoUnidad.EN_RUTA: "enruta",
    EstadoUnidad.EN_ESCENA: "enescena",
    EstadoUnidad.TALLER: "taller",
}

# Tipo de evento -> token de color CSS (clase evento--<token> en la plantilla).
_TOKEN_EVENTO: dict[TipoEvento, str] = {
    TipoEvento.DESPACHO_CREADO: "ok",
    TipoEvento.DESPACHO_FINALIZADO: "ok",
    TipoEvento.DESPACHO_CANCELADO: "crit",
    TipoEvento.REDESPACHO_PROPUESTO: "warn",
    TipoEvento.REDESPACHO_CONFIRMADO: "warn",
    TipoEvento.REDESPACHO_RECHAZADO: "info",
    TipoEvento.UNIDAD_ACTUALIZADA: "info",
}


@dataclass(frozen=True, slots=True)
class _UnidadVM:
    """Vista-modelo de una unidad para la tabla del panel."""

    id: str
    patente: str
    tipo: str
    base_nombre: str
    base_lat: float
    base_lon: float
    estado: str
    estado_token: str
    destino_incidente: str | None = None
    destino_categoria: str | None = None
    destino_eta_segundos: float | None = None


@dataclass(frozen=True, slots=True)
class _EventoVM:
    """Vista-modelo de un evento del log para la consola de auditoría."""

    timestamp: str
    tipo: str
    incidente_id: str
    despacho_id: str
    operador: str
    resumen: str
    token: str


def _cargar_unidades(
    estados: dict[str, EstadoUnidad],
    asignaciones: dict[str, dict[str, Any]] | None = None,
) -> list[_UnidadVM]:
    """Lee la flota desde el dataset y la proyecta a vista-modelos.

    El estado base viene de ``unidades.json``; ``estados`` (overlay en
    memoria) lo sobreescribe para reflejar los despachos hechos desde la
    consola (unidad → ``EnRuta``) hasta el reset. ``asignaciones`` (overlay
    hermano) aporta el destino de cada unidad despachada: incidente,
    categoría y ETA, visibles solo mientras la unidad siga ``EnRuta``.
    """
    datos = json.loads(_UNIDADES_PATH.read_text(encoding="utf-8"))
    asignaciones = asignaciones or {}
    unidades: list[_UnidadVM] = []
    for d in datos:
        estado = estados.get(d["id"], EstadoUnidad(d["estado"]))
        asignacion = asignaciones.get(d["id"]) if estado is EstadoUnidad.EN_RUTA else None
        unidades.append(
            _UnidadVM(
                id=d["id"],
                patente=d["patente"],
                tipo=TipoUnidad(d["tipo"]).value,
                base_nombre=d["base_nombre"],
                base_lat=float(d["base_lat"]),
                base_lon=float(d["base_lon"]),
                estado=estado.value,
                estado_token=_TOKEN_ESTADO[estado],
                destino_incidente=asignacion.get("incidente_id") if asignacion else None,
                destino_categoria=asignacion.get("categoria_mpds") if asignacion else None,
                destino_eta_segundos=asignacion.get("eta_segundos") if asignacion else None,
            )
        )
    return unidades


def _ruta_log_eventos() -> Path:
    """Resuelve el path del log JSONL (env ``SENTINEL_EVENTOS_LOG`` o default)."""
    env = os.environ.get("SENTINEL_EVENTOS_LOG")
    return Path(env) if env else _LOG_EVENTOS_DEFAULT


def cargar_eventos_log() -> list[EventoLog]:
    """Carga los eventos del log JSONL, o lista vacía si el archivo no existe.

    Dependencia FastAPI: los tests la sobreescriben vía
    ``app.dependency_overrides`` para inyectar eventos sin tocar disco.
    """
    ruta = _ruta_log_eventos()
    if not ruta.exists():
        return []
    return list(JsonlRepositorioEventos(ruta).leer_todos())


def _resumen_evento(evento: EventoLog) -> str:
    """Resumen de una línea a partir del payload (shape de ADR-0017)."""
    payload = evento.payload
    partes: list[str] = []
    categoria = payload.get("categoria_mpds")
    if categoria:
        partes.append(str(categoria))
    seleccionada = payload.get("unidad_seleccionada")
    if isinstance(seleccionada, dict) and seleccionada.get("id"):
        partes.append(f"→ {seleccionada['id']}")
    eta = payload.get("eta_segundos")
    if eta is not None:
        partes.append(f"ETA {eta} s")
    motivo = payload.get("motivo")
    if motivo:
        partes.append(str(motivo))
    return " · ".join(partes) if partes else "—"


def _evento_vm(evento: EventoLog) -> _EventoVM:
    return _EventoVM(
        timestamp=evento.timestamp_iso,
        tipo=evento.tipo.value,
        incidente_id=evento.incidente_id or "—",
        despacho_id=evento.despacho_id or "—",
        operador=evento.operador,
        resumen=_resumen_evento(evento),
        token=_TOKEN_EVENTO.get(evento.tipo, "info"),
    )


def obtener_estados_unidades(request: Request) -> dict[str, EstadoUnidad]:
    """Dependencia: overlay en memoria de estados de la flota (consola viva).

    v1 no persiste estado de unidades; este overlay vive en ``app.state`` y
    refleja los despachos hechos desde la consola (unidad → ``EnRuta``) hasta
    el reset. Los tests lo controlan vía ``app.state.estados_unidades``.
    """
    estados = getattr(request.app.state, "estados_unidades", None)
    if estados is None:
        estados = {}
        request.app.state.estados_unidades = estados
    return cast("dict[str, EstadoUnidad]", estados)


def obtener_asignaciones(request: Request) -> dict[str, dict[str, Any]]:
    """Dependencia: overlay en memoria de asignaciones unidad → incidente.

    Complementa :func:`obtener_estados_unidades`: además del estado
    ``EnRuta``, la consola recuerda a qué incidente va cada unidad despachada
    (id, categoría MPDS y ETA) para que el panel de flota lo muestre de un
    vistazo. Mismo ciclo de vida que el overlay de estados (v1, no persiste).
    """
    asignaciones = getattr(request.app.state, "asignaciones_unidades", None)
    if asignaciones is None:
        asignaciones = {}
        request.app.state.asignaciones_unidades = asignaciones
    return cast("dict[str, dict[str, Any]]", asignaciones)


@router.get("/consola/unidades", response_class=HTMLResponse)
async def vista_unidades(
    request: Request,
    estados: dict[str, EstadoUnidad] = Depends(obtener_estados_unidades),
    asignaciones: dict[str, dict[str, Any]] = Depends(obtener_asignaciones),
) -> HTMLResponse:
    """Panel de la flota: tabla de unidades con su estado (RF-09).

    Refleja el overlay en memoria (los despachos hechos desde la consola),
    incluyendo el destino de cada unidad ``EnRuta`` (incidente, categoría,
    ETA) para trazar el vínculo despacho ↔ flota de un vistazo.
    """
    return plantillas.TemplateResponse(
        request=request,
        name="unidades.html",
        context={
            "unidades": _cargar_unidades(estados, asignaciones),
            "vista_activa": "unidades",
        },
    )


@router.get("/consola/log", response_class=HTMLResponse)
async def vista_log(
    request: Request,
    eventos: list[EventoLog] = Depends(cargar_eventos_log),
) -> HTMLResponse:
    """Consola de auditoría: log JSONL append-only de eventos (RF-06)."""
    return plantillas.TemplateResponse(
        request=request,
        name="log.html",
        context={
            "eventos": [_evento_vm(e) for e in eventos],
            "vista_activa": "log",
        },
    )


# ---------------------------------------------------------------------------
# Validación dual RT-02 — Python vs Java lado a lado (ADR-0008)
# ---------------------------------------------------------------------------


@router.get("/consola/validacion", response_class=HTMLResponse)
async def vista_validacion(
    request: Request,
    resultado: ResultadoValidacion = Depends(comparar_validacion_dual),
) -> HTMLResponse:
    """Validación dual RT-02: cálculos de ambos núcleos lado a lado.

    Compara las fixtures commiteadas en ``data/validacion/`` (outputs reales
    de los 12 incidentes del SRS en core-python y core-java) con las mismas
    tolerancias del validador canónico del CI. La comparación corre en cada
    render (ver :mod:`sentinel_dispatch.interfaces.api.validacion`).
    """
    return plantillas.TemplateResponse(
        request=request,
        name="validacion.html",
        context={
            "filas": resultado.filas,
            "resumen": resultado.resumen,
            "fecha_fixtures": FECHA_FIXTURES,
            "vista_activa": "validacion",
        },
    )


# ---------------------------------------------------------------------------
# Despacho con mapa (RF-07) — ADR-0022
# ---------------------------------------------------------------------------

_GRAPH_PATH = _MONOREPO_ROOT / "data" / "graphs" / "coquimbo.graphml"


def _cargar_flota(estados: dict[str, EstadoUnidad]) -> list[Unidad]:
    """Construye la flota del dominio desde el dataset, aplicando el overlay.

    ``estados`` sobreescribe el estado declarado: una unidad marcada
    ``EnRuta`` por un despacho previo queda excluida de la selección
    (``despachar`` solo elige unidades ``Disponible``), simulando flota viva.
    """
    datos = json.loads(_UNIDADES_PATH.read_text(encoding="utf-8"))
    return [
        Unidad(
            id=d["id"],
            patente=d["patente"],
            tipo=TipoUnidad(d["tipo"]),
            base_nombre=d["base_nombre"],
            base_lat=float(d["base_lat"]),
            base_lon=float(d["base_lon"]),
            estado=estados.get(d["id"], EstadoUnidad(d["estado"])),
        )
        for d in datos
    ]


def cargar_grafo_despacho() -> OsmnxGrafoVial:
    """Carga el grafo OSM de la IV Región (lifespan del arranque).

    Operación pesada (~segundos, cientos de MB): se ejecuta una sola vez
    al arrancar el servidor y se guarda en ``app.state`` (ver ``main.py``).
    """
    return OsmnxGrafoVial(cargar_grafo_iv_region(ruta_cache=_GRAPH_PATH))


def crear_repositorio_eventos() -> JsonlRepositorioEventos:
    """Crea el repositorio JSONL de eventos para el log de la consola.

    El despacho desde el mapa escribe un evento ``despacho_creado`` aquí, lo
    que sincroniza la vista de log. Se instancia una sola vez al arranque
    (lifespan) para que el generador de ``evento_id`` sea monotónico entre
    requests y el dedupe por id funcione.
    """
    ruta = _ruta_log_eventos()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    return JsonlRepositorioEventos(ruta)


def obtener_grafo(request: Request) -> GrafoVial:
    """Dependencia: el grafo cacheado en ``app.state``.

    Los tests sobreescriben esta dependencia con un ``GrafoVial`` fake vía
    ``app.dependency_overrides`` para no cargar los 21 MB del grafo real.
    """
    grafo = getattr(request.app.state, "grafo", None)
    if grafo is None:
        raise HTTPException(
            status_code=503,
            detail="Grafo OSM no disponible (el servidor aún está cargándolo).",
        )
    return cast("GrafoVial", grafo)


def obtener_red_vial(request: Request) -> list[list[tuple[float, float]]]:
    """Dependencia: polilíneas de calles principales precomputadas (wireframe)."""
    return cast(
        "list[list[tuple[float, float]]]",
        getattr(request.app.state, "red_vial", []),
    )


def obtener_repositorio_eventos(request: Request) -> JsonlRepositorioEventos | None:
    """Dependencia: el repositorio de eventos, o ``None`` si no está disponible.

    Los tests lo sobreescriben con un fake en memoria; sin override y sin
    lifespan (ASGITransport) devuelve ``None`` y el despacho no escribe al log.
    """
    return cast("JsonlRepositorioEventos | None", getattr(request.app.state, "repo_eventos", None))


@router.get("/consola/despacho", response_class=HTMLResponse)
async def vista_despacho(request: Request) -> HTMLResponse:
    """Página del despacho con mapa: ubicar incidente y ver la ruta A* (RF-07)."""
    return plantillas.TemplateResponse(
        request=request, name="despacho.html", context={"vista_activa": "despacho"}
    )


def _registrar_despacho(repo: JsonlRepositorioEventos, core: dict[str, Any]) -> None:
    """Escribe un evento ``despacho_creado`` al log (best-effort).

    No aborta el despacho si el log falla. El payload reutiliza el dict de
    ``serializar_resultado_despacho`` (ADR-0017), el mismo shape que produce el
    CLI ``run-dataset --log-eventos``; el ``despacho_id`` sigue la convención
    ``SD-<YYYYMMDD>-<seq>`` del CLI.
    """
    evento_id = repo.generar_evento_id()
    evento = EventoLog(
        evento_id=evento_id,
        timestamp_iso=_ahora_iso_z(),
        tipo=TipoEvento.DESPACHO_CREADO,
        despacho_id=f"SD-{datetime.now(UTC).strftime('%Y%m%d')}-{evento_id.rsplit('-', 1)[-1]}",
        incidente_id=str(core.get("incidente_id", "I-CONSOLA")),
        operador="consola_web",
        payload=core,
    )
    try:
        repo.append(evento)
    except EventoDuplicadoError:
        # Colisión de evento_id (raro: mismo segundo tras reinicio). No se aborta
        # el despacho, pero se deja traza para que la omisión sea observable.
        _log.warning("evento_log.duplicado_omitido", extra={"evento_id": evento_id})


@router.post("/consola/despacho/despachar")
async def ejecutar_despacho(
    request: Request,
    lat: float = Form(...),
    lon: float = Form(...),
    categoria_mpds: CategoriaMPDS = Form(...),
    incidente_id: str | None = Form(None),
    grafo: GrafoVial = Depends(obtener_grafo),
    repo: JsonlRepositorioEventos | None = Depends(obtener_repositorio_eventos),
    estados: dict[str, EstadoUnidad] = Depends(obtener_estados_unidades),
    pendientes: dict[str, dict[str, Any]] = Depends(obtener_incidentes_pendientes),
    asignaciones: dict[str, dict[str, Any]] = Depends(obtener_asignaciones),
) -> dict[str, Any]:
    """Despacha la mejor unidad para el incidente clickeado y devuelve JSON.

    Reutiliza ``serializar_resultado_despacho`` (ADR-0017) y le anexa un
    bloque ``geo`` con coordenadas Leaflet (``[lat, lon]``). Además mantiene
    la consola "viva": marca la unidad elegida como ``EnRuta`` en el overlay
    (queda excluida del próximo despacho) y registra un ``despacho_creado``
    en el log JSONL si hay repositorio disponible. Si ``incidente_id``
    referencia una baliza del triaje (overlay de pendientes), el despacho
    exitoso la consume y el evento se loguea con ese id.
    """
    try:
        nodo_incidente = grafo.nodo_mas_cercano(lat, lon)
    except NodoFueraDeRangoError as exc:
        raise HTTPException(
            status_code=422,
            detail={"mensaje": str(exc), "lat": lat, "lon": lon},
        ) from exc

    id_incidente = incidente_id if incidente_id and incidente_id in pendientes else "I-CONSOLA"
    incidente = Incidente(
        id=id_incidente,
        lat=lat,
        lon=lon,
        categoria_mpds=categoria_mpds,
        timestamp_iso=_ahora_iso_z(),
    )
    resultado = despachar(incidente, _cargar_flota(estados), grafo)
    core = serializar_resultado_despacho(resultado)

    # El overlay es estado mutable compartido. Bajo el uvicorn single-worker de
    # v1 no hay race: entre leer la flota y escribir el overlay no hay ``await``.
    # Si se introduce concurrencia/await aquí, envolver con un lock por-app.
    if resultado.elegida is not None:
        estados[resultado.elegida.id] = EstadoUnidad.EN_RUTA
        # Trazabilidad despacho ↔ flota: el panel de unidades muestra a qué
        # incidente va la unidad (id + categoría + ETA) mientras siga EnRuta.
        asignaciones[resultado.elegida.id] = {
            "incidente_id": id_incidente,
            "categoria_mpds": categoria_mpds.value,
            "eta_segundos": core.get("eta_segundos"),
        }
        # Despacho concretado: la baliza del triaje (si la hubo) queda atendida.
        pendientes.pop(id_incidente, None)
    if repo is not None:
        _registrar_despacho(repo, core)

    unidad_base = (
        [resultado.elegida.base_lat, resultado.elegida.base_lon]
        if resultado.elegida is not None
        else None
    )
    return {
        **core,
        "geo": {
            "incidente": [lat, lon],
            "unidad_base": unidad_base,
            "ruta": [list(grafo.coordenadas(n)) for n in resultado.ruta_nodos],
            "snap_m": round(grafo.distancia_snap_m(lat, lon, nodo_incidente), 1),
        },
    }


@router.get("/consola/despacho/red-vial")
async def red_vial(
    calles: list[list[tuple[float, float]]] = Depends(obtener_red_vial),
) -> dict[str, list[list[tuple[float, float]]]]:
    """Polilíneas de las calles principales para el wireframe del mapa (RF-07)."""
    return {"calles": calles}


@router.get("/consola/despacho/incidentes")
async def incidentes_pendientes(
    pendientes: dict[str, dict[str, Any]] = Depends(obtener_incidentes_pendientes),
) -> dict[str, list[dict[str, Any]]]:
    """Balizas pendientes generadas desde el triaje (puente triaje → despacho)."""
    return {"incidentes": list(pendientes.values())}


@router.post("/consola/despacho/reset")
async def reset_flota(
    estados: dict[str, EstadoUnidad] = Depends(obtener_estados_unidades),
    pendientes: dict[str, dict[str, Any]] = Depends(obtener_incidentes_pendientes),
    asignaciones: dict[str, dict[str, Any]] = Depends(obtener_asignaciones),
) -> dict[str, int]:
    """Reinicia la consola: libera la flota y descarta las balizas pendientes."""
    liberadas = len(estados)
    descartados = len(pendientes)
    estados.clear()
    pendientes.clear()
    asignaciones.clear()
    return {"unidades_liberadas": liberadas, "incidentes_descartados": descartados}
