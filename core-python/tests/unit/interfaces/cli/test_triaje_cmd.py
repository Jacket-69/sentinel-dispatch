"""Tests unitarios del CLI ``sentinel triaje``.

Cubren la taxonomía Normal / Borde / Error / Regla de Negocio que exige la
pauta GCS. La capa de dominio (árbol MPDS-subset) ya está cubierta por
:mod:`tests.unit.domain.triaje`; estos tests verifican el **borde**:
parseo de flags, parseo de JSON, propagación de errores y formato del
output del comando ``run-dataset``.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from sentinel_dispatch.interfaces.cli import app

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()


# ---------------------------------------------------------------------------
# classify — Normal
# ---------------------------------------------------------------------------


def test_classify_regla1_paciente_inconsciente_sin_respirar_es_echo() -> None:
    """R1 del árbol: ``not consciente ∧ not respira_normal`` ⇒ Echo."""
    result = runner.invoke(app, ["triaje", "classify", "--no-consciente", "--no-respira-normal"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "Echo"


def test_classify_regla3_sangrado_peligroso_es_delta() -> None:
    """R3 del árbol: sangrado peligroso (zona crítica o arterial) ⇒ Delta."""
    result = runner.invoke(app, ["triaje", "classify", "--sangrado=Peligroso"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "Delta"


def test_classify_regla9_paciente_normal_es_alpha() -> None:
    """R9 (regla por defecto): respuesta consciente sin Chief Complaint ⇒ Alpha."""
    result = runner.invoke(app, ["triaje", "classify"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "Alpha"


# ---------------------------------------------------------------------------
# classify — Borde
# ---------------------------------------------------------------------------


def test_classify_orden_estricto_r1_domina_sobre_r3() -> None:
    """Si paciente inconsciente sin respirar tiene además sangrado peligroso,
    debe salir Echo (R1), no Delta (R3). Verifica orden del árbol."""
    result = runner.invoke(
        app,
        [
            "triaje",
            "classify",
            "--no-consciente",
            "--no-respira-normal",
            "--sangrado=Peligroso",
        ],
    )

    assert result.exit_code == 0
    assert result.stdout.strip() == "Echo"


# ---------------------------------------------------------------------------
# classify — Entrada por JSON (Normal)
# ---------------------------------------------------------------------------


def test_classify_desde_json_replica_dataset_i07() -> None:
    """JSON inline equivalente al incidente I-07 del dataset (Delta)."""
    payload = json.dumps(
        {
            "consciente": True,
            "respira_normal": True,
            "sangrado": "Ninguno",
            "dolor_toracico": "Crítico",
            "dificultad_respiratoria": False,
            "grupo_etario": "Adulto",
        }
    )
    result = runner.invoke(app, ["triaje", "classify", "--json", payload])

    assert result.exit_code == 0
    assert result.stdout.strip() == "Delta"


# ---------------------------------------------------------------------------
# classify — Error
# ---------------------------------------------------------------------------


def test_classify_rechaza_json_malformado() -> None:
    """JSON inválido debe terminar con exit code != 0 y mensaje al stderr."""
    result = runner.invoke(app, ["triaje", "classify", "--json", "{not valid"])

    assert result.exit_code == 2
    assert "JSON inválido" in result.stderr


def test_classify_rechaza_enum_de_sangrado_invalido() -> None:
    """Valor fuera del :class:`NivelSangrado` debe ser rechazado por Typer."""
    result = runner.invoke(app, ["triaje", "classify", "--sangrado=Profuso"])

    assert result.exit_code != 0
    assert "Profuso" in result.stderr or "Profuso" in result.output


# ---------------------------------------------------------------------------
# run-dataset — Regla de Negocio + Error
# ---------------------------------------------------------------------------


def test_run_dataset_real_clasifica_12_de_12_y_exit_cero() -> None:
    """El dataset versionado debe clasificarse perfectamente (RT-02 base)."""
    result = runner.invoke(app, ["triaje", "run-dataset"])

    assert result.exit_code == 0
    assert "12/12" in result.stdout


def test_run_dataset_falla_si_archivo_no_existe(tmp_path: Path) -> None:
    """Path inexistente: exit code 2 y mensaje claro en stderr."""
    inexistente = tmp_path / "no-existe.json"

    result = runner.invoke(app, ["triaje", "run-dataset", "--dataset", str(inexistente)])

    assert result.exit_code == 2
    assert "no encontrado" in result.stderr


def test_run_dataset_detecta_divergencia_con_ground_truth_y_exit_uno(tmp_path: Path) -> None:
    """Dataset alterado donde la categoría esperada miente: exit 1."""
    fake = tmp_path / "fake.json"
    fake.write_text(
        json.dumps(
            [
                {
                    "id": "I-FAKE",
                    "respuestas_triaje": {
                        "consciente": True,
                        "respira_normal": True,
                        "sangrado": "Ninguno",
                        "dolor_toracico": "Ninguno",
                        "dificultad_respiratoria": False,
                        "grupo_etario": "Adulto",
                    },
                    "ground_truth": {"categoria_mpds": "Echo"},  # Es realmente Alpha.
                }
            ]
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["triaje", "run-dataset", "--dataset", str(fake)])

    assert result.exit_code == 1
    assert "0/1" in result.stdout


# ---------------------------------------------------------------------------
# Entry-point raíz
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("flag", ["--help"])
def test_root_app_muestra_ayuda(flag: str) -> None:
    """``sentinel --help`` no debe explotar y debe listar el subcomando triaje."""
    result = runner.invoke(app, [flag])

    assert result.exit_code == 0
    assert "triaje" in result.stdout
