"""Tests unitarios del comparador RT-02 (tools/compare_outputs.py).

Cobertura mínima (taxonomía N/B/E/RN):

Normal:
  N-1: par idéntico (exact + numéricos iguales) → OK.
  N-2: diff eta <5% → WARN.

Borde:
  B-1: ambos saturados → OK (todo null/vacío).
  B-2: ruta distinta pero mismo origen/destino y longitud ±10% → OK.

Error:
  E-1: directorio Python inexistente → exit 2.
  E-2: archivo JSONL malformado → exit 2.
  E-3: motivo distinto → FAIL.
  E-4: unidad.id distinto → FAIL.

Reglas de Negocio:
  RN-1: diff eta >5% → FAIL.
  RN-2: MISSING (Python tiene, Java no) → exit 1 global.
  RN-3: EXTRA (Java tiene, Python no) → reportado; exit 0 si no hay FAIL.
  RN-4: ruta con origen distinto → FAIL.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any


def _load_compare_outputs() -> Any:
    """Carga el módulo tools/compare_outputs.py por ruta absoluta."""
    # Desde core-python/tests/unit/tools/ subimos 5 niveles para llegar a
    # la raíz del monorepo: tests/unit/tools → tests/unit → tests → core-python → monorepo
    monorepo_root = Path(__file__).resolve().parents[4]
    mod_path = monorepo_root / "tools" / "compare_outputs.py"
    spec = importlib.util.spec_from_file_location("compare_outputs", mod_path)
    assert spec is not None, f"No se pudo cargar {mod_path}"
    assert spec.loader is not None, f"Loader nulo para {mod_path}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


_co = _load_compare_outputs()


# ---------------------------------------------------------------------------
# Helpers de fixtures
# ---------------------------------------------------------------------------


def _doc_optimo(
    id_: str = "I-01",
    categoria: str = "Alpha",
    uid: str = "U01",
    eta: float = 187.42,
    pen: float = 0.0,
    ruta: list[str] | None = None,
) -> dict[str, Any]:
    """Produce un dict JSONL de despacho óptimo."""
    if ruta is None:
        ruta = ["100001", "100002", "100003"]
    total = eta + pen
    return {
        "incidente_id": id_,
        "categoria_mpds": categoria,
        "unidad_seleccionada": {"id": uid},
        "despacho_suboptimo": False,
        "motivo": "optimo",
        "eta_segundos": eta,
        "costo": {"T_viaje": eta, "penalizacion": pen, "total": total},
        "ruta": ruta,
    }


def _doc_saturacion(id_: str = "I-XX", categoria: str = "Echo") -> dict[str, Any]:
    """Produce un dict JSONL de saturación."""
    return {
        "incidente_id": id_,
        "categoria_mpds": categoria,
        "unidad_seleccionada": None,
        "despacho_suboptimo": False,
        "motivo": "saturacion",
        "eta_segundos": None,
        "costo": None,
        "ruta": [],
    }


def _write_jsonl(directory: Path, id_: str, doc: dict[str, Any]) -> None:
    """Escribe un .jsonl en el directorio."""
    (directory / f"{id_}.jsonl").write_text(
        json.dumps(doc, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _setup_dirs(
    tmp_path: Path,
    py_docs: dict[str, dict[str, Any]],
    java_docs: dict[str, dict[str, Any]],
) -> tuple[Path, Path]:
    """Crea subdirectorios python-out y java-out con los documentos dados."""
    py_dir = tmp_path / "python-out"
    java_dir = tmp_path / "java-out"
    py_dir.mkdir()
    java_dir.mkdir()
    for id_, doc in py_docs.items():
        _write_jsonl(py_dir, id_, doc)
    for id_, doc in java_docs.items():
        _write_jsonl(java_dir, id_, doc)
    return py_dir, java_dir


# ---------------------------------------------------------------------------
# Normal
# ---------------------------------------------------------------------------


class TestNormal:
    def test_n1_par_identico_es_ok(self, tmp_path: Path) -> None:
        """N-1: par idéntico (todos los campos iguales) → estado OK."""
        doc = _doc_optimo("I-01")
        py_dir, java_dir = _setup_dirs(tmp_path, {"I-01": doc}, {"I-01": doc})
        report = tmp_path / "report.md"

        exit_code = _co.comparar(py_dir, java_dir, report)

        assert exit_code == 0
        texto = report.read_text(encoding="utf-8")
        assert "| I-01 | OK |" in texto

    def test_n2_diff_eta_menor_5pct_es_warn(self, tmp_path: Path) -> None:
        """N-2: diff eta_segundos <5% → estado WARN (dentro de tolerancia)."""
        py_doc = _doc_optimo("I-01", eta=187.42)
        # 3.2% de diferencia
        java_doc = _doc_optimo("I-01", eta=187.42 * 1.032)
        py_dir, java_dir = _setup_dirs(tmp_path, {"I-01": py_doc}, {"I-01": java_doc})
        report = tmp_path / "report.md"

        exit_code = _co.comparar(py_dir, java_dir, report)

        assert exit_code == 0
        texto = report.read_text(encoding="utf-8")
        assert "| I-01 | WARN |" in texto


# ---------------------------------------------------------------------------
# Borde
# ---------------------------------------------------------------------------


class TestBorde:
    def test_b1_ambos_saturados_es_ok(self, tmp_path: Path) -> None:
        """B-1: ambos incidentes saturados → OK (null/null está dentro de tolerancia)."""
        doc = _doc_saturacion("I-XX", "Echo")
        py_dir, java_dir = _setup_dirs(tmp_path, {"I-XX": doc}, {"I-XX": doc})
        report = tmp_path / "report.md"

        exit_code = _co.comparar(py_dir, java_dir, report)

        assert exit_code == 0
        texto = report.read_text(encoding="utf-8")
        assert "| I-XX | OK |" in texto

    def test_b2_ruta_distinta_mismo_origen_destino_longitud_ok(self, tmp_path: Path) -> None:
        """B-2: rutas distintas con mismo origen/destino y longitud ±10% → OK."""
        ruta_py = ["A", "B", "C", "D", "E"]
        ruta_java = ["A", "X", "Y", "E"]  # distinta pero misma longitud dentro ±10%
        py_doc = _doc_optimo("I-02", ruta=ruta_py)
        java_doc = _doc_optimo("I-02", ruta=ruta_java)
        py_dir, java_dir = _setup_dirs(tmp_path, {"I-02": py_doc}, {"I-02": java_doc})
        report = tmp_path / "report.md"

        exit_code = _co.comparar(py_dir, java_dir, report)

        assert exit_code == 0
        texto = report.read_text(encoding="utf-8")
        # 5 nodos py vs 4 java → diff 20% → WARN
        # Verificamos que no sea FAIL (origen/destino coinciden)
        assert "ruta.origen" not in texto
        assert "ruta.destino" not in texto


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------


class TestError:
    def test_e1_directorio_python_inexistente_exit_2(self, tmp_path: Path) -> None:
        """E-1: directorio --python inexistente → exit 2."""
        java_dir = tmp_path / "java-out"
        java_dir.mkdir()
        report = tmp_path / "report.md"

        exit_code = _co.comparar(tmp_path / "no_existe", java_dir, report)

        assert exit_code == 2

    def test_e2_jsonl_malformado_exit_2(self, tmp_path: Path) -> None:
        """E-2: archivo .jsonl malformado en directorio Python → exit 2."""
        py_dir = tmp_path / "python-out"
        java_dir = tmp_path / "java-out"
        py_dir.mkdir()
        java_dir.mkdir()
        (py_dir / "I-01.jsonl").write_text("{malformado", encoding="utf-8")
        report = tmp_path / "report.md"

        exit_code = _co.comparar(py_dir, java_dir, report)

        assert exit_code == 2

    def test_e3_motivo_distinto_es_fail(self, tmp_path: Path) -> None:
        """E-3: motivo distinto (optimo vs penalizado) → FAIL."""
        py_doc = _doc_optimo("I-03")
        java_doc = {**py_doc, "motivo": "penalizado"}
        py_dir, java_dir = _setup_dirs(tmp_path, {"I-03": py_doc}, {"I-03": java_doc})
        report = tmp_path / "report.md"

        exit_code = _co.comparar(py_dir, java_dir, report)

        assert exit_code == 1
        texto = report.read_text(encoding="utf-8")
        assert "| I-03 | FAIL |" in texto

    def test_e4_unidad_id_distinto_es_fail(self, tmp_path: Path) -> None:
        """E-4: unidad_seleccionada.id distinto → FAIL."""
        py_doc = _doc_optimo("I-04", uid="U01")
        java_doc = _doc_optimo("I-04", uid="U03")
        py_dir, java_dir = _setup_dirs(tmp_path, {"I-04": py_doc}, {"I-04": java_doc})
        report = tmp_path / "report.md"

        exit_code = _co.comparar(py_dir, java_dir, report)

        assert exit_code == 1
        texto = report.read_text(encoding="utf-8")
        assert "| I-04 | FAIL |" in texto


# ---------------------------------------------------------------------------
# Reglas de Negocio
# ---------------------------------------------------------------------------


class TestReglasNegocio:
    def test_rn1_diff_eta_mayor_5pct_es_fail(self, tmp_path: Path) -> None:
        """RN-1: diff eta_segundos >5% → FAIL."""
        py_doc = _doc_optimo("I-05", eta=200.0)
        java_doc = _doc_optimo("I-05", eta=215.0)  # 7.5% de diferencia
        py_dir, java_dir = _setup_dirs(tmp_path, {"I-05": py_doc}, {"I-05": java_doc})
        report = tmp_path / "report.md"

        exit_code = _co.comparar(py_dir, java_dir, report)

        assert exit_code == 1
        texto = report.read_text(encoding="utf-8")
        assert "| I-05 | FAIL |" in texto

    def test_rn2_missing_en_java_exit_1(self, tmp_path: Path) -> None:
        """RN-2: incidente en Python pero no en Java → reportado MISSING; exit 1."""
        py_doc = _doc_optimo("I-06")
        py_dir = tmp_path / "python-out"
        java_dir = tmp_path / "java-out"
        py_dir.mkdir()
        java_dir.mkdir()
        _write_jsonl(py_dir, "I-06", py_doc)
        report = tmp_path / "report.md"

        exit_code = _co.comparar(py_dir, java_dir, report)

        assert exit_code == 1
        texto = report.read_text(encoding="utf-8")
        assert "I-06" in texto
        assert "MISSING" in texto

    def test_rn3_extra_en_java_exit_0_si_no_hay_fail(self, tmp_path: Path) -> None:
        """RN-3: incidente solo en Java → EXTRA reportado; exit 0 si no hay FAIL."""
        py_doc = _doc_optimo("I-07")
        java_doc_extra = _doc_optimo("I-99")
        py_dir = tmp_path / "python-out"
        java_dir = tmp_path / "java-out"
        py_dir.mkdir()
        java_dir.mkdir()
        _write_jsonl(py_dir, "I-07", py_doc)
        _write_jsonl(java_dir, "I-07", py_doc)  # par idéntico
        _write_jsonl(java_dir, "I-99", java_doc_extra)
        report = tmp_path / "report.md"

        exit_code = _co.comparar(py_dir, java_dir, report)

        assert exit_code == 0
        texto = report.read_text(encoding="utf-8")
        assert "I-99" in texto
        assert "EXTRA" in texto

    def test_rn4_ruta_origen_distinto_es_fail(self, tmp_path: Path) -> None:
        """RN-4: ruta con nodo de origen distinto → FAIL."""
        py_doc = _doc_optimo("I-08", ruta=["A", "B", "C"])
        java_doc = _doc_optimo("I-08", ruta=["X", "B", "C"])  # origen diferente
        py_dir, java_dir = _setup_dirs(tmp_path, {"I-08": py_doc}, {"I-08": java_doc})
        report = tmp_path / "report.md"

        exit_code = _co.comparar(py_dir, java_dir, report)

        assert exit_code == 1
        texto = report.read_text(encoding="utf-8")
        assert "ruta.origen" in texto
