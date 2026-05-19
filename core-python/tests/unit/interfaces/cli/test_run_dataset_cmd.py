"""Tests unitarios del subcomando ``run-dataset`` del CLI.

Cobertura mínima según pauta GCS (Normal/Borde/Error/RN):

Normal:
  - Un incidente Alpha + flota disponible → produce .jsonl con schema completo.
  - Motivo OPTIMO queda serializado correctamente (eta_segundos, costo, unidad).

Borde:
  - Dataset vacío → 0 archivos producidos, exit 0.
  - Directorio de salida inexistente → se crea automáticamente.

Error:
  - ``--in`` apunta a archivo inexistente → exit 2, mensaje en stderr.
  - JSON malformado en ``--in`` → exit 2.

Regla de Negocio:
  - Incidente Echo + única Básica disponible → motivo=suboptimo_rn02,
    ``despacho_suboptimo=true`` en el JSONL (RN-02).

Los tests usan monkeypatch para reemplazar la carga real del GraphML
(21 MB) con un FakeGrafo y forzar tiempos de A* sintéticos.
Ningún test carga el GraphML real — la suite corre en ~1s sin I/O GIS.
"""

from __future__ import annotations

import json
import math
from typing import TYPE_CHECKING, Any

import pytest
from typer.testing import CliRunner

import sentinel_dispatch.application.despachar_ambulancia as _da
import sentinel_dispatch.interfaces.cli.run_dataset_cmd as _rdc
from sentinel_dispatch.domain.routing.tipos import Arista, NoRutaDisponibleError
from sentinel_dispatch.interfaces.cli import app

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()

# ---------------------------------------------------------------------------
# FakeGrafo — misma semántica que en test_despacho.py
# ---------------------------------------------------------------------------


class FakeGrafo:
    """Grafo trivial para tests: snap determinista, aristas mínimas."""

    def __init__(
        self,
        nodos_por_unidad: dict[str, int],
        nodo_incidente: int = 99,
        coords_por_nodo: dict[int, tuple[float, float]] | None = None,
    ) -> None:
        self._nodos = nodos_por_unidad
        self._nodo_inc = nodo_incidente
        self._coords: dict[int, tuple[float, float]] = {99: (-29.92, -71.26)}
        if coords_por_nodo:
            self._coords.update(coords_por_nodo)
        else:
            for idx, nid in enumerate(dict.fromkeys(nodos_por_unidad.values())):
                if nid not in self._coords:
                    self._coords[nid] = (-29.9077, -71.2535 - idx * 0.001)

    def vecinos(self, nodo: int) -> list[Arista]:
        if nodo != self._nodo_inc:
            return [
                Arista(
                    origen=nodo,
                    destino=self._nodo_inc,
                    longitud_m=1000.0,
                    velocidad_efectiva_kmh=50.0,
                )
            ]
        return []

    def coordenadas(self, nodo: int) -> tuple[float, float]:
        return self._coords[nodo]

    def nodo_mas_cercano(self, lat: float, lon: float) -> int:
        if abs(lat - (-29.92)) < 0.01 and abs(lon - (-71.26)) < 0.01:
            return self._nodo_inc
        mejor_nid = 1
        mejor_dist = float("inf")
        for nid, (cy, cx) in self._coords.items():
            if nid == self._nodo_inc:
                continue
            d = (lat - cy) ** 2 + (lon - cx) ** 2
            if d < mejor_dist:
                mejor_dist = d
                mejor_nid = nid
        return mejor_nid

    def distancia_snap_m(self, lat: float, lon: float, nodo: int) -> float:
        return 0.0


# ---------------------------------------------------------------------------
# Helpers para construir datasets JSON mínimos
# ---------------------------------------------------------------------------

_UNIDAD_AVANZADA: dict[str, Any] = {
    "id": "U01",
    "patente": "AMB-001",
    "tipo": "Avanzada",
    "base_nombre": "Hospital Test",
    "base_lat": -29.9077,
    "base_lon": -71.2535,
    "estado": "Disponible",
}

_UNIDAD_BASICA: dict[str, Any] = {
    "id": "U02",
    "patente": "AMB-002",
    "tipo": "Básica",
    "base_nombre": "CESFAM Test",
    "base_lat": -29.9015,
    "base_lon": -71.2433,
    "estado": "Disponible",
}


def _incidente_json(
    id_: str = "I-01",
    lat: float = -29.92,
    lon: float = -71.26,
    categoria: str = "Alpha",
) -> dict[str, Any]:
    return {
        "id": id_,
        "lat": lat,
        "lon": lon,
        "timestamp": "2026-05-25T08:15:00-04:00",
        "respuestas_triaje": {
            "consciente": True,
            "respira_normal": True,
            "sangrado": "Ninguno",
            "dolor_toracico": "Ninguno",
            "dificultad_respiratoria": False,
            "grupo_etario": "Adulto",
        },
        "ground_truth": {
            "categoria_mpds": categoria,
            "unidad_esperada": "U01",
            "eta_aprox_min": 3,
            "regla_aplicada": 9,
            "nota": "Test fixture.",
        },
    }


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Fixture: fake carga de grafo + a_estrella
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_grafo_y_tiempos(monkeypatch: pytest.MonkeyPatch) -> dict[str, float]:
    """Monta FakeGrafo + a_estrella fake para toda la suite.

    Retorna el dict de tiempos; el test lo modifica antes de invocar el CLI.
    """
    tiempos: dict[str, float] = {"U01": 187.42, "U02": 250.0}

    # Coords explícitas para que nodo_mas_cercano mapee inequívocamente:
    # U01 base: (-29.9077, -71.2535) → nodo 1
    # U02 base: (-29.9015, -71.2433) → nodo 2
    # Cada base tiene coords propias; la distancia mínima queda determinada.
    fake = FakeGrafo(
        nodos_por_unidad={"U01": 1, "U02": 2},
        coords_por_nodo={
            1: (-29.9077, -71.2535),
            2: (-29.9015, -71.2433),
        },
    )

    def fake_cargar(*_: Any, **__: Any) -> FakeGrafo:
        """Devuelve el FakeGrafo; OsmnxGrafoVial lo recibe como argumento grafo."""
        return fake

    class FakeOsmnxGrafoVial:
        """Stub de OsmnxGrafoVial: devuelve el FakeGrafo en lugar del wrapper real."""

        def __new__(cls, grafo: Any) -> FakeGrafo:  # type: ignore[misc]
            return fake

    def fake_a_estrella(
        grafo_arg: Any,
        origen: int,
        destino: int,
        factor_hora: float,
        factor_sirena: float,
    ) -> tuple[float, list[int]]:
        for uid, nid in fake._nodos.items():
            if nid == origen:
                t = tiempos.get(uid)
                if t is None:
                    raise NoRutaDisponibleError(f"sin t para {uid}")
                if t == math.inf:
                    raise NoRutaDisponibleError(f"inf para {uid}")
                return (t, [origen, destino])
        raise NoRutaDisponibleError("origen desconocido")

    monkeypatch.setattr(_rdc, "cargar_grafo_iv_region", fake_cargar)
    monkeypatch.setattr(_rdc, "OsmnxGrafoVial", FakeOsmnxGrafoVial)
    monkeypatch.setattr(_da, "a_estrella", fake_a_estrella)
    return tiempos


def _invoke(
    tmp_path: Path,
    incidentes: list[Any],
    unidades: list[Any],
    out_dir: Path,
    *,
    graph_name: str = "fake.graphml",
    graph_content: str = "<graphml/>",
    extra_args: list[str] | None = None,
) -> Any:
    """Helper para invocar el CLI con archivos temporales."""
    in_file = tmp_path / "incidentes.json"
    unidades_file = tmp_path / "unidades.json"
    graph_file = tmp_path / graph_name
    _write_json(in_file, incidentes)
    _write_json(unidades_file, unidades)
    graph_file.write_text(graph_content, encoding="utf-8")

    args = [
        "run-dataset",
        "--in",
        str(in_file),
        "--unidades",
        str(unidades_file),
        "--graph",
        str(graph_file),
        "--out",
        str(out_dir),
    ]
    if extra_args:
        args.extend(extra_args)
    return runner.invoke(app, args)


# ---------------------------------------------------------------------------
# Normal — camino feliz
# ---------------------------------------------------------------------------


class TestNormal:
    def test_un_incidente_alpha_produce_jsonl_con_schema_completo(
        self,
        fake_grafo_y_tiempos: dict[str, float],
        tmp_path: Path,
    ) -> None:
        """Normal-1: 1 incidente Alpha + Avanzada disponible → JSONL con todos los campos."""
        out_dir = tmp_path / "out"
        result = _invoke(
            tmp_path,
            incidentes=[_incidente_json("I-01", categoria="Alpha")],
            unidades=[_UNIDAD_AVANZADA],
            out_dir=out_dir,
        )

        assert result.exit_code == 0, result.output
        out_file = out_dir / "I-01.jsonl"
        assert out_file.exists()

        data = json.loads(out_file.read_text(encoding="utf-8"))
        assert data["incidente_id"] == "I-01"
        assert data["categoria_mpds"] == "Alpha"
        assert data["despacho_suboptimo"] is False
        assert data["motivo"] == "optimo"
        assert data["eta_segundos"] == pytest.approx(187.42)
        assert data["unidad_seleccionada"] == {"id": "U01"}
        assert data["costo"] is not None
        assert "T_viaje" in data["costo"]
        assert "penalizacion" in data["costo"]
        assert "total" in data["costo"]
        # La ruta debe estar poblada para un despacho exitoso (H3-J-1b)
        ruta = data["ruta"]
        assert isinstance(ruta, list)
        assert len(ruta) >= 2, "La ruta de un despacho exitoso debe tener al menos 2 nodos"
        # Los IDs de nodo se serializan como strings (ADR-0017 §ruta)
        assert all(isinstance(n, str) for n in ruta)
        assert all(int(n) >= 0 for n in ruta), "Cada elemento debe parsear a entero no negativo"

    def test_motivo_optimo_serializado_correctamente(
        self,
        fake_grafo_y_tiempos: dict[str, float],
        tmp_path: Path,
    ) -> None:
        """Normal-2: Alpha + flota con Avanzada → motivo=optimo y costo.penalizacion=0."""
        out_dir = tmp_path / "out2"
        result = _invoke(
            tmp_path,
            incidentes=[_incidente_json("I-02", categoria="Alpha")],
            unidades=[_UNIDAD_AVANZADA],
            out_dir=out_dir,
        )

        assert result.exit_code == 0
        data = json.loads((out_dir / "I-02.jsonl").read_text(encoding="utf-8"))
        assert data["motivo"] == "optimo"
        assert data["costo"]["penalizacion"] == pytest.approx(0.0)
        assert data["costo"]["total"] == pytest.approx(data["costo"]["T_viaje"])


# ---------------------------------------------------------------------------
# Borde
# ---------------------------------------------------------------------------


class TestBorde:
    def test_dataset_vacio_produce_cero_archivos(
        self,
        fake_grafo_y_tiempos: dict[str, float],
        tmp_path: Path,
    ) -> None:
        """Borde-1: dataset con 0 incidentes → 0 archivos en out, exit 0."""
        out_dir = tmp_path / "out_vacio"
        result = _invoke(
            tmp_path,
            incidentes=[],
            unidades=[_UNIDAD_AVANZADA],
            out_dir=out_dir,
        )

        assert result.exit_code == 0
        # El directorio puede no existir (dataset vacío sale antes de mkdir)
        # o existir y estar vacío.
        if out_dir.exists():
            jsonl_files = list(out_dir.glob("*.jsonl"))
            assert len(jsonl_files) == 0

    def test_directorio_out_inexistente_se_crea(
        self,
        fake_grafo_y_tiempos: dict[str, float],
        tmp_path: Path,
    ) -> None:
        """Borde-2: ``--out`` apunta a dir inexistente → se crea y el archivo se escribe."""
        out_dir = tmp_path / "nuevo" / "subdir" / "salida"
        assert not out_dir.exists()

        result = _invoke(
            tmp_path,
            incidentes=[_incidente_json("I-03")],
            unidades=[_UNIDAD_AVANZADA],
            out_dir=out_dir,
        )

        assert result.exit_code == 0
        assert out_dir.exists()
        assert (out_dir / "I-03.jsonl").exists()


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------


class TestError:
    def test_incidentes_archivo_inexistente_exit_2(self, tmp_path: Path) -> None:
        """Error-1: ``--in`` apunta a archivo que no existe → exit 2."""
        result = runner.invoke(
            app,
            [
                "run-dataset",
                "--in",
                str(tmp_path / "no_existe.json"),
                "--unidades",
                str(tmp_path / "u.json"),
                "--graph",
                str(tmp_path / "g.graphml"),
                "--out",
                str(tmp_path / "out"),
            ],
        )

        assert result.exit_code == 2

    def test_incidentes_json_malformado_exit_2(self, tmp_path: Path) -> None:
        """Error-2: JSON malformado en ``--in`` → exit 2."""
        in_file = tmp_path / "malformed.json"
        unidades_file = tmp_path / "u.json"
        graph_file = tmp_path / "g.graphml"
        in_file.write_text("{no es json valido", encoding="utf-8")
        _write_json(unidades_file, [_UNIDAD_AVANZADA])
        graph_file.write_text("<graphml/>", encoding="utf-8")

        result = runner.invoke(
            app,
            [
                "run-dataset",
                "--in",
                str(in_file),
                "--unidades",
                str(unidades_file),
                "--graph",
                str(graph_file),
                "--out",
                str(tmp_path / "out"),
            ],
        )

        assert result.exit_code == 2


# ---------------------------------------------------------------------------
# Reglas de Negocio
# ---------------------------------------------------------------------------


class TestReglasNegocio:
    def test_echo_unica_basica_es_suboptimo_rn02(
        self,
        fake_grafo_y_tiempos: dict[str, float],
        tmp_path: Path,
    ) -> None:
        """RN-02: Echo + única unidad Básica → motivo=suboptimo_rn02, despacho_suboptimo=true."""
        # Ajustar tiempos para la Básica (U02)
        fake_grafo_y_tiempos["U02"] = 200.0

        out_dir = tmp_path / "out_rn02"
        result = _invoke(
            tmp_path,
            incidentes=[_incidente_json("I-10", categoria="Echo")],
            unidades=[_UNIDAD_BASICA],
            out_dir=out_dir,
        )

        assert result.exit_code == 0, result.output
        data = json.loads((out_dir / "I-10.jsonl").read_text(encoding="utf-8"))
        assert data["motivo"] == "suboptimo_rn02"
        assert data["despacho_suboptimo"] is True
        assert data["unidad_seleccionada"] == {"id": "U02"}
        assert data["eta_segundos"] == pytest.approx(200.0)
        # RN-02: la ruta de la Básica elegida también se incluye en el JSONL
        ruta = data["ruta"]
        assert isinstance(ruta, list)
        assert len(ruta) >= 2, "El fallback RN-02 también debe tener ruta"
        assert all(isinstance(n, str) for n in ruta)
