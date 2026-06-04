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
import os
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
from sentinel_dispatch.ports.repositorio_eventos import EventoLog, TipoEvento

if TYPE_CHECKING:
    from sentinel_dispatch.domain.routing.grafo_vial import GrafoVial

_DIR_BASE = Path(__file__).parent
DIRECTORIO_PLANTILLAS = _DIR_BASE / "templates"
DIRECTORIO_ESTATICOS = _DIR_BASE / "static"

plantillas = Jinja2Templates(directory=str(DIRECTORIO_PLANTILLAS))

router = APIRouter(tags=["consola"])

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


@router.post("/consola/triaje/clasificar", response_class=HTMLResponse)
async def clasificar_triaje(
    request: Request,
    consciente: bool = Form(...),
    respira_normal: bool = Form(...),
    sangrado: NivelSangrado = Form(...),
    dolor_toracico: NivelDolorToracico = Form(...),
    dificultad_respiratoria: bool = Form(...),
    grupo_etario: GrupoEtario = Form(...),
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
    return plantillas.TemplateResponse(
        request=request,
        name="_resultado_triaje.html",
        context={
            "categoria": categoria.value,
            "severidad": severidad,
            "descripcion": descripcion,
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


def _cargar_unidades() -> list[_UnidadVM]:
    """Lee la flota desde el dataset y la proyecta a vista-modelos.

    Los estados son los declarados en ``unidades.json``; v1 no modela
    evolución temporal de la flota, así que el panel refleja ese estado.
    """
    datos = json.loads(_UNIDADES_PATH.read_text(encoding="utf-8"))
    unidades: list[_UnidadVM] = []
    for d in datos:
        estado = EstadoUnidad(d["estado"])
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


@router.get("/consola/unidades", response_class=HTMLResponse)
async def vista_unidades(request: Request) -> HTMLResponse:
    """Panel de la flota: tabla de unidades con su estado (RF-09)."""
    return plantillas.TemplateResponse(
        request=request,
        name="unidades.html",
        context={"unidades": _cargar_unidades(), "vista_activa": "unidades"},
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
# Despacho con mapa (RF-07) — ADR-0022
# ---------------------------------------------------------------------------

_GRAPH_PATH = _MONOREPO_ROOT / "data" / "graphs" / "coquimbo.graphml"


def _cargar_flota() -> list[Unidad]:
    """Construye la flota de :class:`Unidad` del dominio desde el dataset."""
    datos = json.loads(_UNIDADES_PATH.read_text(encoding="utf-8"))
    return [
        Unidad(
            id=d["id"],
            patente=d["patente"],
            tipo=TipoUnidad(d["tipo"]),
            base_nombre=d["base_nombre"],
            base_lat=float(d["base_lat"]),
            base_lon=float(d["base_lon"]),
            estado=EstadoUnidad(d["estado"]),
        )
        for d in datos
    ]


def cargar_grafo_despacho() -> GrafoVial:
    """Carga el grafo OSM de la IV Región (lifespan del arranque).

    Operación pesada (~segundos, cientos de MB): se ejecuta una sola vez
    al arrancar el servidor y se guarda en ``app.state`` (ver ``main.py``).
    """
    return OsmnxGrafoVial(cargar_grafo_iv_region(ruta_cache=_GRAPH_PATH))


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


@router.get("/consola/despacho", response_class=HTMLResponse)
async def vista_despacho(request: Request) -> HTMLResponse:
    """Página del despacho con mapa: ubicar incidente y ver la ruta A* (RF-07)."""
    return plantillas.TemplateResponse(
        request=request, name="despacho.html", context={"vista_activa": "despacho"}
    )


@router.post("/consola/despacho/despachar")
async def ejecutar_despacho(
    request: Request,
    lat: float = Form(...),
    lon: float = Form(...),
    categoria_mpds: CategoriaMPDS = Form(...),
    grafo: GrafoVial = Depends(obtener_grafo),
) -> dict[str, Any]:
    """Despacha la mejor unidad para el incidente clickeado y devuelve JSON.

    Reutiliza ``serializar_resultado_despacho`` (ADR-0017) y le anexa un
    bloque ``geo`` con coordenadas listas para Leaflet (orden ``[lat, lon]``):
    incidente, base de la unidad elegida, ruta A* y distancia de snap (RN-09).
    """
    try:
        nodo_incidente = grafo.nodo_mas_cercano(lat, lon)
    except NodoFueraDeRangoError as exc:
        raise HTTPException(
            status_code=422,
            detail={"mensaje": str(exc), "lat": lat, "lon": lon},
        ) from exc

    incidente = Incidente(
        id="I-CONSOLA",
        lat=lat,
        lon=lon,
        categoria_mpds=categoria_mpds,
        timestamp_iso=datetime.now(UTC).isoformat(),
    )
    resultado = despachar(incidente, _cargar_flota(), grafo)

    payload = serializar_resultado_despacho(resultado)
    unidad_base = (
        [resultado.elegida.base_lat, resultado.elegida.base_lon]
        if resultado.elegida is not None
        else None
    )
    payload["geo"] = {
        "incidente": [lat, lon],
        "unidad_base": unidad_base,
        "ruta": [list(grafo.coordenadas(n)) for n in resultado.ruta_nodos],
        "snap_m": round(grafo.distancia_snap_m(lat, lon, nodo_incidente), 1),
    }
    return payload
