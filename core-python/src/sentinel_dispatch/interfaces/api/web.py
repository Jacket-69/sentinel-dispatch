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

from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from sentinel_dispatch.domain.triaje import (
    CategoriaMPDS,
    GrupoEtario,
    NivelDolorToracico,
    NivelSangrado,
    RespuestaTriaje,
    clasificar_mpds,
)

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
    return plantillas.TemplateResponse(request=request, name="triaje.html")


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
