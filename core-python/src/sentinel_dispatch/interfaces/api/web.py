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
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from sentinel_dispatch.adapters.repositorio_jsonl import JsonlRepositorioEventos
from sentinel_dispatch.domain.dispatch.tipos import EstadoUnidad, TipoUnidad
from sentinel_dispatch.domain.triaje import (
    CategoriaMPDS,
    GrupoEtario,
    NivelDolorToracico,
    NivelSangrado,
    RespuestaTriaje,
    clasificar_mpds,
)
from sentinel_dispatch.ports.repositorio_eventos import EventoLog, TipoEvento

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
