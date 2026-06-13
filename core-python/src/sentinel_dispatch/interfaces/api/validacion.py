"""Comparación server-side para la vista de validación dual RT-02.

Carga los outputs JSONL commiteados de ambos núcleos
(``data/validacion/python/`` y ``data/validacion/java/``) y produce filas
comparadas por incidente para que la consola evidencie la paridad Python ↔
Java (RT-02, ADR-0008). Las tolerancias espejan ``tools/compare_outputs.py``
(el validador canónico que corre en el job ``compare`` del CI):

- Exact match: ``categoria_mpds``, ``unidad_seleccionada.id``,
  ``despacho_suboptimo``, ``motivo``.
- ±5 %: ``eta_segundos``, ``costo.T_viaje``, ``costo.penalizacion``,
  ``costo.total`` — pero siempre se expone el **delta real** (hoy 0.000 %).
- Ruta: mismo primer y último nodo (exacto); longitud ±10 %.

La comparación se computa en cada render (es barata: 24 archivos de una
línea); no se precomputa ni se cachea el resultado.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Path canónico relativo al monorepo, misma convención que web.py:
# validacion.py → [0] api/ → [1] interfaces/ → [2] sentinel_dispatch/
# → [3] src/ → [4] core-python/ → [5] sentinel-dispatch/ (raíz monorepo)
_MONOREPO_ROOT = Path(__file__).resolve().parents[5]
DIR_FIXTURES_PYTHON = _MONOREPO_ROOT / "data" / "validacion" / "python"
DIR_FIXTURES_JAVA = _MONOREPO_ROOT / "data" / "validacion" / "java"

# Fecha de generación de las fixtures commiteadas (footer de procedencia).
# Mantener sincronizada con data/validacion/README.md al regenerarlas.
FECHA_FIXTURES = "2026-06-12"

# Tolerancias — espejo de tools/compare_outputs.py (ADR-0008).
TOLERANCIA_NUMERICA = 0.05  # ±5% para campos numéricos
TOLERANCIA_LARGO_RUTA = 0.10  # ±10% para longitud de ruta

# Campos numéricos comparados con tolerancia; los dos primeros se muestran
# como columnas propias en la tabla, todos pesan en el veredicto de la fila.
_CAMPOS_NUMERICOS = ("eta_segundos", "costo.T_viaje", "costo.penalizacion", "costo.total")


# ---------------------------------------------------------------------------
# Vista-modelos
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ComparacionExacta:
    """Par de valores que deben coincidir exactamente entre núcleos."""

    python: str
    java: str
    estado: str  # "ok" | "fail"


@dataclass(frozen=True, slots=True)
class ComparacionNumerica:
    """Par numérico con tolerancia ±5 % y delta porcentual real."""

    python: float | None
    java: float | None
    delta_pct: float | None  # delta real en %, None si no comparable
    estado: str  # "ok" | "warn" | "fail"


@dataclass(frozen=True, slots=True)
class ComparacionRuta:
    """Ruta A*: extremos exactos + largo con tolerancia ±10 %."""

    nodos_python: int
    nodos_java: int
    extremos_coinciden: bool
    delta_largo_pct: float | None
    estado: str  # "ok" | "warn" | "fail"


@dataclass(frozen=True, slots=True)
class FilaValidacion:
    """Una fila de la tabla: un incidente comparado entre ambos núcleos.

    Si el incidente falta en uno de los lados, ``veredicto`` es ``MISSING``
    y los campos comparados quedan en ``None`` (la plantilla colapsa la fila).
    """

    incidente_id: str
    veredicto: str  # "OK" | "WARN" | "FAIL" | "MISSING"
    notas: tuple[str, ...]
    categoria: ComparacionExacta | None = None
    unidad: ComparacionExacta | None = None
    eta: ComparacionNumerica | None = None
    costo_total: ComparacionNumerica | None = None
    ruta: ComparacionRuta | None = None


@dataclass(frozen=True, slots=True)
class ResumenValidacion:
    """Agregado de la corrida completa (banner de la vista)."""

    total: int
    ok: int
    warn: int
    fail: int
    missing: int
    delta_eta_max_pct: float
    delta_costo_max_pct: float

    @property
    def paridad(self) -> bool:
        """True si los 12/12 dieron OK (sin WARN, FAIL ni MISSING)."""
        return self.total > 0 and self.ok == self.total


@dataclass(frozen=True, slots=True)
class ResultadoValidacion:
    """Filas comparadas + resumen agregado, listo para la plantilla."""

    filas: list[FilaValidacion]
    resumen: ResumenValidacion


# ---------------------------------------------------------------------------
# Comparación (espejo de tools/compare_outputs.py)
# ---------------------------------------------------------------------------

_ORDEN_ESTADO = {"ok": 0, "warn": 1, "fail": 2}


def _estado_peor(a: str, b: str) -> str:
    """Retorna el estado más grave entre dos (fail > warn > ok)."""
    return a if _ORDEN_ESTADO.get(a, 0) >= _ORDEN_ESTADO.get(b, 0) else b


def _pct_diff(a: float, b: float) -> float:
    """Diferencia porcentual relativa (fracción), misma fórmula del validador CI."""
    if a == 0.0 and b == 0.0:
        return 0.0
    return abs(a - b) / max(abs(a), abs(b))


def _campo_anidado(doc: dict[str, Any], campo: str) -> Any:
    """Extrae un campo posiblemente anidado como ``costo.T_viaje``."""
    partes = campo.split(".", 1)
    if len(partes) == 1:
        return doc.get(campo)
    padre = doc.get(partes[0])
    if not isinstance(padre, dict):
        return None
    return padre.get(partes[1])


def _comparar_exacto(py_val: Any, java_val: Any) -> ComparacionExacta:
    """Compara un par exact-match y lo proyecta a strings presentables."""
    return ComparacionExacta(
        python="—" if py_val is None else str(py_val),
        java="—" if java_val is None else str(java_val),
        estado="ok" if py_val == java_val else "fail",
    )


def _comparar_numerico(py_val: Any, java_val: Any) -> ComparacionNumerica:
    """Compara un par numérico con tolerancia ±5 %, exponiendo el delta real."""
    if py_val is None and java_val is None:
        return ComparacionNumerica(python=None, java=None, delta_pct=None, estado="ok")
    if (py_val is None) != (java_val is None):
        return ComparacionNumerica(
            python=None if py_val is None else float(py_val),
            java=None if java_val is None else float(java_val),
            delta_pct=None,
            estado="fail",
        )
    delta = _pct_diff(float(py_val), float(java_val))
    if delta > TOLERANCIA_NUMERICA:
        estado = "fail"
    elif delta > 0.0:
        estado = "warn"
    else:
        estado = "ok"
    return ComparacionNumerica(
        python=float(py_val), java=float(java_val), delta_pct=delta * 100, estado=estado
    )


def _comparar_ruta(py_ruta: list[Any], java_ruta: list[Any]) -> ComparacionRuta:
    """Compara las rutas A*: extremos exactos, largo ±10 %.

    Ambas vacías (saturación en los dos núcleos) cuenta como paridad; una
    sola vacía es FAIL (un núcleo encontró ruta y el otro no).
    """
    if not py_ruta and not java_ruta:
        return ComparacionRuta(
            nodos_python=0,
            nodos_java=0,
            extremos_coinciden=True,
            delta_largo_pct=0.0,
            estado="ok",
        )
    if not py_ruta or not java_ruta:
        return ComparacionRuta(
            nodos_python=len(py_ruta),
            nodos_java=len(java_ruta),
            extremos_coinciden=False,
            delta_largo_pct=None,
            estado="fail",
        )
    extremos = py_ruta[0] == java_ruta[0] and py_ruta[-1] == java_ruta[-1]
    delta_largo = _pct_diff(float(len(py_ruta)), float(len(java_ruta)))
    estado = "ok"
    if not extremos:
        estado = "fail"
    elif delta_largo > TOLERANCIA_LARGO_RUTA:
        estado = "warn"
    return ComparacionRuta(
        nodos_python=len(py_ruta),
        nodos_java=len(java_ruta),
        extremos_coinciden=extremos,
        delta_largo_pct=delta_largo * 100,
        estado=estado,
    )


def _unidad_id(doc: dict[str, Any]) -> str | None:
    """``unidad_seleccionada.id``, o None si el despacho saturó (sin unidad)."""
    if doc.get("motivo") == "saturacion":
        return None
    unidad = doc.get("unidad_seleccionada")
    if not isinstance(unidad, dict):
        return None
    id_ = unidad.get("id")
    return None if id_ is None else str(id_)


def comparar_incidente(
    incidente_id: str, py_doc: dict[str, Any], java_doc: dict[str, Any]
) -> FilaValidacion:
    """Compara los outputs de un mismo incidente y produce la fila de la vista.

    El veredicto agrega todos los campos del contrato RT-02 (incluidos
    ``costo.T_viaje``, ``costo.penalizacion``, ``despacho_suboptimo`` y
    ``motivo``, que no tienen columna propia); cualquier diferencia fuera
    del comportamiento esperado queda anotada en ``notas``.
    """
    estado = "ok"
    notas: list[str] = []

    categoria = _comparar_exacto(py_doc.get("categoria_mpds"), java_doc.get("categoria_mpds"))
    unidad = _comparar_exacto(_unidad_id(py_doc), _unidad_id(java_doc))
    suboptimo = _comparar_exacto(
        py_doc.get("despacho_suboptimo"), java_doc.get("despacho_suboptimo")
    )
    motivo = _comparar_exacto(py_doc.get("motivo"), java_doc.get("motivo"))
    for nombre, comp in (
        ("categoria_mpds", categoria),
        ("unidad.id", unidad),
        ("despacho_suboptimo", suboptimo),
        ("motivo", motivo),
    ):
        if comp.estado == "fail":
            notas.append(f"{nombre}: py={comp.python} vs java={comp.java}")
            estado = _estado_peor(estado, "fail")

    numericos: dict[str, ComparacionNumerica] = {}
    for campo in _CAMPOS_NUMERICOS:
        comp_num = _comparar_numerico(
            _campo_anidado(py_doc, campo), _campo_anidado(java_doc, campo)
        )
        numericos[campo] = comp_num
        if comp_num.estado != "ok":
            delta = "—" if comp_num.delta_pct is None else f"{comp_num.delta_pct:.3f}%"
            notas.append(f"{campo}: delta {delta} ({comp_num.estado})")
        estado = _estado_peor(estado, comp_num.estado)

    ruta = _comparar_ruta(py_doc.get("ruta") or [], java_doc.get("ruta") or [])
    if ruta.estado != "ok":
        notas.append(
            f"ruta: nodos py={ruta.nodos_python} java={ruta.nodos_java}"
            f" extremos={'=' if ruta.extremos_coinciden else '≠'}"
        )
    estado = _estado_peor(estado, ruta.estado)

    return FilaValidacion(
        incidente_id=incidente_id,
        veredicto=estado.upper(),
        notas=tuple(notas),
        categoria=categoria,
        unidad=unidad,
        eta=numericos["eta_segundos"],
        costo_total=numericos["costo.total"],
        ruta=ruta,
    )


# ---------------------------------------------------------------------------
# Carga de fixtures + resultado agregado
# ---------------------------------------------------------------------------


def _cargar_documentos(directorio: Path) -> dict[str, dict[str, Any]]:
    """Carga los ``*.jsonl`` (uno por incidente) como dict id → documento.

    Directorio inexistente o archivo malformado degradan a "lado vacío"
    (la fila sale MISSING): la vista nunca revienta por fixtures rotas.
    """
    documentos: dict[str, dict[str, Any]] = {}
    if not directorio.is_dir():
        return documentos
    for archivo in sorted(directorio.glob("*.jsonl")):
        try:
            doc = json.loads(archivo.read_text(encoding="utf-8").strip())
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(doc, dict):
            documentos[archivo.stem] = doc
    return documentos


def comparar_validacion_dual(
    dir_python: Path = DIR_FIXTURES_PYTHON,
    dir_java: Path = DIR_FIXTURES_JAVA,
) -> ResultadoValidacion:
    """Compara los outputs de ambos núcleos y arma el resultado de la vista.

    Dependencia FastAPI de la vista ``/consola/validacion``; los tests la
    sobreescriben vía ``app.dependency_overrides`` o la invocan directo con
    directorios temporales.
    """
    py_docs = _cargar_documentos(dir_python)
    java_docs = _cargar_documentos(dir_java)

    filas: list[FilaValidacion] = []
    for id_ in sorted(set(py_docs) | set(java_docs)):
        if id_ not in py_docs or id_ not in java_docs:
            lado = "core-python" if id_ not in py_docs else "core-java"
            filas.append(
                FilaValidacion(
                    incidente_id=id_,
                    veredicto="MISSING",
                    notas=(f"sin output en {lado}",),
                )
            )
            continue
        filas.append(comparar_incidente(id_, py_docs[id_], java_docs[id_]))

    deltas_eta = [
        f.eta.delta_pct for f in filas if f.eta is not None and f.eta.delta_pct is not None
    ]
    deltas_costo = [
        f.costo_total.delta_pct
        for f in filas
        if f.costo_total is not None and f.costo_total.delta_pct is not None
    ]
    resumen = ResumenValidacion(
        total=len(filas),
        ok=sum(1 for f in filas if f.veredicto == "OK"),
        warn=sum(1 for f in filas if f.veredicto == "WARN"),
        fail=sum(1 for f in filas if f.veredicto == "FAIL"),
        missing=sum(1 for f in filas if f.veredicto == "MISSING"),
        delta_eta_max_pct=max(deltas_eta, default=0.0),
        delta_costo_max_pct=max(deltas_costo, default=0.0),
    )
    return ResultadoValidacion(filas=filas, resumen=resumen)
