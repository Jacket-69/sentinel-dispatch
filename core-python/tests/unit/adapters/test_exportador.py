"""UT del exportador CSV/JSON (RF-11)."""

from __future__ import annotations

import csv
import json
from typing import TYPE_CHECKING, Any

from typer.testing import CliRunner

from sentinel_dispatch.adapters.exportador import (
    _aplanar_dict,
    exportar_a_csv,
    exportar_a_json,
)
from sentinel_dispatch.adapters.repositorio_jsonl import JsonlRepositorioEventos
from sentinel_dispatch.interfaces.cli import app
from sentinel_dispatch.ports.repositorio_eventos import EventoLog, TipoEvento

if TYPE_CHECKING:
    from pathlib import Path


runner = CliRunner()


def _evento(
    evento_id: str = "EVT-20260521T120000-0001",
    *,
    payload: dict[str, Any] | None = None,
) -> EventoLog:
    return EventoLog(
        evento_id=evento_id,
        timestamp_iso="2026-05-21T12:00:00.000Z",
        tipo=TipoEvento.DESPACHO_CREADO,
        despacho_id="SD-20260521-0001",
        incidente_id="I-01",
        payload=payload
        or {
            "motivo": "optimo",
            "costo": {"T_viaje": 187.42, "penalizacion": 0.0, "total": 187.42},
            "unidad_seleccionada": {"id": "U02"},
            "ruta": ["123456", "234567"],
        },
    )


# ---------------------------------------------------------------------------
# _aplanar_dict
# ---------------------------------------------------------------------------


class TestAplanarDict:
    def test_dict_anidado_se_concatena_con_underscore(self) -> None:
        data = {"costo": {"T_viaje": 1.0, "total": 1.0}}
        plano = _aplanar_dict(data, prefijo="payload")
        assert plano == {"payload_costo_T_viaje": 1.0, "payload_costo_total": 1.0}

    def test_lista_se_serializa_a_json_string(self) -> None:
        data = {"ruta": ["123", "456"]}
        plano = _aplanar_dict(data, prefijo="p")
        assert plano["p_ruta"] == '["123", "456"]'

    def test_sin_prefijo_concatena_solo_keys(self) -> None:
        data = {"a": {"b": 1}}
        plano = _aplanar_dict(data)
        assert plano == {"a_b": 1}


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------


class TestExportarCsv:
    def test_normal_3_eventos_3_filas_con_header(self, tmp_path: Path) -> None:
        destino = tmp_path / "reporte.csv"
        n = exportar_a_csv([_evento(f"EVT-{i:04d}") for i in range(3)], destino)
        assert n == 3
        # Lectura con utf-8-sig (consume BOM)
        with destino.open(encoding="utf-8-sig", newline="") as f:
            filas = list(csv.DictReader(f))
        assert len(filas) == 3
        assert filas[0]["evento_id"] == "EVT-0000"
        assert filas[0]["payload_motivo"] == "optimo"
        assert filas[0]["payload_costo_total"] == "187.42"

    def test_borde_lista_vacia_solo_header_minimal(self, tmp_path: Path) -> None:
        destino = tmp_path / "reporte.csv"
        n = exportar_a_csv([], destino)
        assert n == 0
        contenido = destino.read_text(encoding="utf-8-sig")
        # Solo el header de las columnas raíz (sin payload_*).
        assert contenido.strip() == "evento_id,timestamp_iso,tipo,despacho_id,incidente_id,operador"

    def test_payloads_heterogeneos_union_de_columnas(self, tmp_path: Path) -> None:
        """Si un evento tiene una columna que otro no, ambas existen y la
        celda faltante queda vacía."""
        destino = tmp_path / "reporte.csv"
        n = exportar_a_csv(
            [
                _evento("EVT-A", payload={"motivo": "optimo", "eta_segundos": 100}),
                _evento("EVT-B", payload={"motivo": "saturacion"}),
            ],
            destino,
        )
        assert n == 2
        with destino.open(encoding="utf-8-sig", newline="") as f:
            filas = list(csv.DictReader(f))
        assert filas[0]["payload_eta_segundos"] == "100"
        assert filas[1]["payload_eta_segundos"] == ""

    def test_utf8_sig_emite_bom_para_excel(self, tmp_path: Path) -> None:
        destino = tmp_path / "reporte.csv"
        exportar_a_csv([_evento()], destino)
        # Primeros 3 bytes deben ser BOM utf-8 (EF BB BF).
        assert destino.read_bytes()[:3] == b"\xef\xbb\xbf"


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------


class TestExportarJson:
    def test_normal_3_eventos_produce_array_de_3_objetos(self, tmp_path: Path) -> None:
        destino = tmp_path / "reporte.json"
        n = exportar_a_json([_evento(f"EVT-{i:04d}") for i in range(3)], destino)
        assert n == 3
        data = json.loads(destino.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert len(data) == 3
        assert data[0]["evento_id"] == "EVT-0000"
        assert data[0]["payload"]["motivo"] == "optimo"

    def test_borde_lista_vacia_produce_array_vacio(self, tmp_path: Path) -> None:
        destino = tmp_path / "reporte.json"
        n = exportar_a_json([], destino)
        assert n == 0
        contenido = destino.read_text(encoding="utf-8")
        assert json.loads(contenido) == []

    def test_json_sin_bom(self, tmp_path: Path) -> None:
        destino = tmp_path / "reporte.json"
        exportar_a_json([_evento()], destino)
        assert destino.read_bytes()[:3] != b"\xef\xbb\xbf"


# ---------------------------------------------------------------------------
# CLI: sentinel export
# ---------------------------------------------------------------------------


class TestCliExport:
    def test_cli_export_csv_end_to_end(self, tmp_path: Path) -> None:
        """Smoke: escribe un JSONL, invoca `sentinel export --formato csv`, parsea."""
        eventos_path = tmp_path / "eventos.jsonl"
        repo = JsonlRepositorioEventos(eventos_path)
        repo.append(_evento("EVT-X-0001"))
        repo.append(_evento("EVT-X-0002"))

        out_csv = tmp_path / "out.csv"
        result = runner.invoke(
            app,
            ["export", "--formato", "csv", "--in", str(eventos_path), "--out", str(out_csv)],
        )
        assert result.exit_code == 0, result.output
        assert out_csv.exists()
        with out_csv.open(encoding="utf-8-sig", newline="") as f:
            filas = list(csv.DictReader(f))
        assert len(filas) == 2

    def test_cli_export_json_end_to_end(self, tmp_path: Path) -> None:
        eventos_path = tmp_path / "eventos.jsonl"
        repo = JsonlRepositorioEventos(eventos_path)
        repo.append(_evento("EVT-Y-0001"))

        out_json = tmp_path / "out.json"
        result = runner.invoke(
            app,
            ["export", "--formato", "json", "--in", str(eventos_path), "--out", str(out_json)],
        )
        assert result.exit_code == 0
        data = json.loads(out_json.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert data[0]["evento_id"] == "EVT-Y-0001"

    def test_cli_export_archivo_inexistente_exit_2(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app,
            [
                "export",
                "--formato",
                "csv",
                "--in",
                str(tmp_path / "no-existe.jsonl"),
                "--out",
                str(tmp_path / "out.csv"),
            ],
        )
        assert result.exit_code == 2
        assert "no encontrado" in result.stderr

    def test_cli_export_jsonl_corrupto_exit_2(self, tmp_path: Path) -> None:
        eventos_path = tmp_path / "corrupto.jsonl"
        eventos_path.write_text('{"evento_id": "X", "campo_invalido": 1}\n', encoding="utf-8")
        result = runner.invoke(
            app,
            [
                "export",
                "--formato",
                "csv",
                "--in",
                str(eventos_path),
                "--out",
                str(tmp_path / "out.csv"),
            ],
        )
        assert result.exit_code == 2
