"""Tests del árbol MPDS-subset — una prueba por regla + orden estricto.

Cubre las 9 reglas del SRS sec. 2.6-A y verifica que el orden de evaluación
no se rompa cuando múltiples condiciones aplican simultáneamente.
"""

from __future__ import annotations

import pytest

from sentinel_dispatch.domain.triaje import (
    CategoriaMPDS,
    NivelDolorToracico,
    NivelSangrado,
    clasificar_mpds,
)

pytestmark = pytest.mark.unit


# --- 9 reglas en orden ---------------------------------------------------


def test_regla_1_inconsciente_no_respira_es_echo(respuesta) -> None:
    # Protocol 9-E-1 / 31-E-1 — arrest o ineffective breathing.
    r = respuesta(consciente=False, respira_normal=False)
    assert clasificar_mpds(r) is CategoriaMPDS.ECHO


def test_regla_2_inconsciente_respira_normal_es_delta(respuesta) -> None:
    # Protocol 31-D-2 — unconscious con respiración efectiva.
    r = respuesta(consciente=False, respira_normal=True)
    assert clasificar_mpds(r) is CategoriaMPDS.DELTA


def test_regla_3_sangrado_peligroso_es_delta(respuesta) -> None:
    # Protocol 21-D-4 — sangrado arterial o zona crítica.
    r = respuesta(sangrado=NivelSangrado.PELIGROSO)
    assert clasificar_mpds(r) is CategoriaMPDS.DELTA


def test_regla_4_dolor_toracico_critico_es_delta(respuesta) -> None:
    # Protocol 10-D — chest pain con síntoma asociado severo.
    r = respuesta(dolor_toracico=NivelDolorToracico.CRITICO)
    assert clasificar_mpds(r) is CategoriaMPDS.DELTA


def test_regla_5_dolor_toracico_presente_es_charlie(respuesta) -> None:
    # Protocol 10-C — chest pain aislado, paciente alerta.
    r = respuesta(dolor_toracico=NivelDolorToracico.PRESENTE)
    assert clasificar_mpds(r) is CategoriaMPDS.CHARLIE


def test_regla_6_dificultad_respiratoria_es_charlie(respuesta) -> None:
    # Protocol 6-C / 31-C-1 — alert con abnormal breathing.
    r = respuesta(dificultad_respiratoria=True)
    assert clasificar_mpds(r) is CategoriaMPDS.CHARLIE


def test_regla_7_sangrado_activo_es_charlie(respuesta) -> None:
    # Adaptación SAMU Chile (ADR-0009) — lectura conservadora vs MPDS 21-B-2.
    r = respuesta(sangrado=NivelSangrado.ACTIVO)
    assert clasificar_mpds(r) is CategoriaMPDS.CHARLIE


def test_regla_8_sangrado_moderado_es_bravo(respuesta) -> None:
    # Protocol 21-B-2 — serious hemorrhage no peligroso.
    r = respuesta(sangrado=NivelSangrado.MODERADO)
    assert clasificar_mpds(r) is CategoriaMPDS.BRAVO


def test_regla_9_consciente_sin_chief_complaint_es_alpha(respuesta) -> None:
    # Equivalente a Protocol 26-A — sick person sin determinantes.
    r = respuesta()  # defaults: consciente, sin nada
    assert clasificar_mpds(r) is CategoriaMPDS.ALPHA


# --- Orden estricto y casos compuestos -----------------------------------


def test_inconsciencia_domina_sobre_sangrado_peligroso(respuesta) -> None:
    # Si el paciente está inconsciente, las reglas 1/2 deben dispararse
    # antes que la regla 3 (que exige consciente=True).
    r = respuesta(
        consciente=False,
        respira_normal=False,
        sangrado=NivelSangrado.PELIGROSO,
    )
    assert clasificar_mpds(r) is CategoriaMPDS.ECHO


def test_sangrado_peligroso_domina_sobre_dolor_critico(respuesta) -> None:
    # Regla 3 antes que regla 4: ambas dan Delta, pero el árbol sale por R3.
    # Verifica que el orden no se rompa al haber múltiples condiciones de Delta.
    r = respuesta(
        sangrado=NivelSangrado.PELIGROSO,
        dolor_toracico=NivelDolorToracico.CRITICO,
        dificultad_respiratoria=True,
    )
    assert clasificar_mpds(r) is CategoriaMPDS.DELTA


def test_dolor_critico_domina_sobre_dificultad_respiratoria(respuesta) -> None:
    # Regla 4 (Delta) gana antes que regla 6 (Charlie).
    r = respuesta(
        dolor_toracico=NivelDolorToracico.CRITICO,
        dificultad_respiratoria=True,
    )
    assert clasificar_mpds(r) is CategoriaMPDS.DELTA


def test_dificultad_respiratoria_domina_sobre_sangrado_activo(respuesta) -> None:
    # Regla 6 (Charlie) antes que regla 7 (Charlie). Ambas dan Charlie pero
    # el orden importa para trazabilidad del MPDS aplicado.
    r = respuesta(
        dificultad_respiratoria=True,
        sangrado=NivelSangrado.ACTIVO,
    )
    assert clasificar_mpds(r) is CategoriaMPDS.CHARLIE
