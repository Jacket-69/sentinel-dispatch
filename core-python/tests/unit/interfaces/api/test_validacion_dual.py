"""Tests unitarios del módulo de validación dual RT-02 (interfaces/api/validacion.py).

Las tolerancias espejan ``tools/compare_outputs.py`` (validador canónico del
CI); estos tests fijan esa semántica en la capa de la vista.

Cobertura (taxonomía N/B/E/RN):

Normal:
  N-1: paridad exacta (todos los campos idénticos) → OK, deltas 0.000 %.
  N-2: resumen agregado consistente (conteos + deltas máximos + paridad).

Borde:
  B-1: numérico dentro de tolerancia (>0, ≤5 %) → WARN con delta real.
  B-2: ambos núcleos saturados (sin unidad, ruta vacía) → OK.
  B-3: largo de ruta fuera de ±10 % con extremos iguales → WARN.

Error:
  E-1: numérico fuera de tolerancia (>5 %) → FAIL.
  E-2: extremos de ruta distintos → FAIL.
  E-3: archivo faltante en un lado → MISSING.
  E-4: campo exacto distinto (unidad.id) → FAIL.

Reglas de Negocio:
  RN-1: directorios inexistentes → resultado vacío sin reventar.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

from sentinel_dispatch.interfaces.api.validacion import (
    comparar_incidente,
    comparar_validacion_dual,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _doc(
    eta: float = 77.16079826274049,
    total: float | None = None,
    uid: str | None = "U09",
    ruta: list[str] | None = None,
    motivo: str = "optimo",
) -> dict[str, Any]:
    """Documento JSONL mínimo con el shape congelado en ADR-0017."""
    if total is None:
        total = eta
    if ruta is None:
        ruta = ["311738976", "1223748567", "311738981"]
    return {
        "incidente_id": "I-01",
        "categoria_mpds": "Alpha",
        "unidad_seleccionada": None if uid is None else {"id": uid},
        "despacho_suboptimo": False,
        "motivo": motivo,
        "eta_segundos": eta,
        "costo": {"T_viaje": eta, "penalizacion": 0.0, "total": total},
        "ruta": ruta,
    }


def _doc_saturado() -> dict[str, Any]:
    """Documento de saturación: sin unidad, sin ruta, numéricos en null."""
    return {
        "incidente_id": "I-01",
        "categoria_mpds": "Echo",
        "unidad_seleccionada": None,
        "despacho_suboptimo": False,
        "motivo": "saturacion",
        "eta_segundos": None,
        "costo": {"T_viaje": None, "penalizacion": None, "total": None},
        "ruta": [],
    }


def _escribir_fixtures(directorio: Path, docs: dict[str, dict[str, Any]]) -> Path:
    directorio.mkdir(parents=True, exist_ok=True)
    for id_, doc in docs.items():
        (directorio / f"{id_}.jsonl").write_text(json.dumps(doc) + "\n", encoding="utf-8")
    return directorio


# ---------------------------------------------------------------------------
# Normal
# ---------------------------------------------------------------------------


def test_paridad_exacta_da_ok_con_delta_cero() -> None:
    fila = comparar_incidente("I-01", _doc(), _doc())
    assert fila.veredicto == "OK"
    assert fila.notas == ()
    assert fila.eta is not None
    assert fila.eta.delta_pct == 0.0
    assert fila.eta.estado == "ok"
    assert fila.costo_total is not None
    assert fila.costo_total.delta_pct == 0.0
    assert fila.ruta is not None
    assert fila.ruta.extremos_coinciden
    assert fila.ruta.estado == "ok"


def test_resumen_agrega_conteos_y_deltas_maximos(tmp_path: Path) -> None:
    dir_py = _escribir_fixtures(
        tmp_path / "python", {"I-01": _doc(), "I-02": _doc(eta=100.0), "I-03": _doc()}
    )
    dir_java = _escribir_fixtures(
        tmp_path / "java",
        {"I-01": _doc(), "I-02": _doc(eta=104.0)},  # I-02 → WARN 4%; I-03 falta → MISSING
    )
    resultado = comparar_validacion_dual(dir_python=dir_py, dir_java=dir_java)
    resumen = resultado.resumen
    assert resumen.total == 3
    assert (resumen.ok, resumen.warn, resumen.fail, resumen.missing) == (1, 1, 0, 1)
    assert resumen.delta_eta_max_pct > 3.8
    assert resumen.delta_eta_max_pct <= 4.0
    assert not resumen.paridad


# ---------------------------------------------------------------------------
# Borde
# ---------------------------------------------------------------------------


def test_numerico_dentro_de_tolerancia_da_warn_con_delta_real() -> None:
    # 2% de diferencia: dentro del ±5%, pero la paridad ya no es exacta.
    fila = comparar_incidente("I-01", _doc(eta=100.0, total=100.0), _doc(eta=102.0, total=102.0))
    assert fila.veredicto == "WARN"
    assert fila.eta is not None
    assert fila.eta.estado == "warn"
    assert fila.eta.delta_pct is not None
    assert 1.9 < fila.eta.delta_pct < 2.0  # delta real: 2/102 ≈ 1.961%
    assert any("eta_segundos" in nota for nota in fila.notas)


def test_ambos_saturados_da_ok() -> None:
    fila = comparar_incidente("I-07", _doc_saturado(), _doc_saturado())
    assert fila.veredicto == "OK"
    assert fila.unidad is not None
    assert fila.unidad.python == "—"
    assert fila.unidad.estado == "ok"
    assert fila.eta is not None
    assert fila.eta.delta_pct is None
    assert fila.ruta is not None
    assert fila.ruta.nodos_python == 0
    assert fila.ruta.estado == "ok"


def test_largo_de_ruta_fuera_de_tolerancia_da_warn() -> None:
    # Mismos extremos, pero 3 vs 20 nodos (>10% de diferencia de largo).
    ruta_larga = ["A"] + [f"N{i}" for i in range(18)] + ["Z"]
    fila = comparar_incidente("I-01", _doc(ruta=["A", "M", "Z"]), _doc(ruta=ruta_larga))
    assert fila.veredicto == "WARN"
    assert fila.ruta is not None
    assert fila.ruta.extremos_coinciden
    assert fila.ruta.estado == "warn"


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------


def test_numerico_fuera_de_tolerancia_da_fail() -> None:
    fila = comparar_incidente("I-01", _doc(eta=100.0, total=100.0), _doc(eta=110.0, total=110.0))
    assert fila.veredicto == "FAIL"
    assert fila.eta is not None
    assert fila.eta.estado == "fail"
    assert fila.eta.delta_pct is not None
    assert fila.eta.delta_pct > 5.0


def test_extremos_de_ruta_distintos_da_fail() -> None:
    fila = comparar_incidente("I-01", _doc(ruta=["A", "M", "Z"]), _doc(ruta=["B", "M", "Z"]))
    assert fila.veredicto == "FAIL"
    assert fila.ruta is not None
    assert not fila.ruta.extremos_coinciden
    assert fila.ruta.estado == "fail"


def test_archivo_faltante_en_un_lado_da_missing(tmp_path: Path) -> None:
    dir_py = _escribir_fixtures(tmp_path / "python", {"I-01": _doc(), "I-02": _doc()})
    dir_java = _escribir_fixtures(tmp_path / "java", {"I-01": _doc()})
    resultado = comparar_validacion_dual(dir_python=dir_py, dir_java=dir_java)
    assert [f.veredicto for f in resultado.filas] == ["OK", "MISSING"]
    faltante = resultado.filas[1]
    assert faltante.incidente_id == "I-02"
    assert faltante.categoria is None
    assert "core-java" in faltante.notas[0]


def test_unidad_distinta_da_fail() -> None:
    fila = comparar_incidente("I-01", _doc(uid="U09"), _doc(uid="U03"))
    assert fila.veredicto == "FAIL"
    assert fila.unidad is not None
    assert fila.unidad.estado == "fail"
    assert any("unidad.id" in nota for nota in fila.notas)


# ---------------------------------------------------------------------------
# Reglas de negocio
# ---------------------------------------------------------------------------


def test_directorios_inexistentes_degradan_a_resultado_vacio(tmp_path: Path) -> None:
    resultado = comparar_validacion_dual(
        dir_python=tmp_path / "no-existe-py", dir_java=tmp_path / "no-existe-java"
    )
    assert resultado.filas == []
    assert resultado.resumen.total == 0
    assert not resultado.resumen.paridad
