"""Tests de los tipos del dominio de triaje (enums y dataclass)."""

from __future__ import annotations

import dataclasses

import pytest

from sentinel_dispatch.domain.triaje import (
    CategoriaMPDS,
    NivelDolorToracico,
    NivelSangrado,
    RespuestaTriaje,
)


pytestmark = pytest.mark.unit


class TestCategoriaMPDS:
    """Orden estricto y comparación de :class:`CategoriaMPDS`."""

    def test_orden_estricto_alpha_a_echo(self) -> None:
        # Criticidad creciente declarada en el SRS sec. 2.6-A.
        assert (
            CategoriaMPDS.ALPHA
            < CategoriaMPDS.BRAVO
            < CategoriaMPDS.CHARLIE
            < CategoriaMPDS.DELTA
            < CategoriaMPDS.ECHO
        )

    def test_no_es_estrictamente_menor_que_si_misma(self) -> None:
        assert not (CategoriaMPDS.DELTA < CategoriaMPDS.DELTA)

    def test_orden_es_transitivo(self) -> None:
        # Si Alpha < Charlie y Charlie < Echo entonces Alpha < Echo.
        # Cubre que el orden no se rompa por alguna implementación rara.
        assert CategoriaMPDS.ALPHA < CategoriaMPDS.CHARLIE
        assert CategoriaMPDS.CHARLIE < CategoriaMPDS.ECHO
        assert CategoriaMPDS.ALPHA < CategoriaMPDS.ECHO


class TestEnumsRespuesta:
    """Valores de los enums de respuesta (alineados a SRS sec. 2.5)."""

    def test_nivel_sangrado_tiene_cuatro_niveles(self) -> None:
        assert {n.value for n in NivelSangrado} == {
            "Ninguno",
            "Moderado",
            "Activo",
            "Peligroso",
        }

    def test_nivel_dolor_toracico_tiene_tres_niveles(self) -> None:
        assert {n.value for n in NivelDolorToracico} == {"Ninguno", "Presente", "Crítico"}


class TestRespuestaTriaje:
    """Dataclass inmutable de las respuestas del operador."""

    def test_es_inmutable(self, respuesta) -> None:
        # frozen=True ⇒ FrozenInstanceError al intentar mutar.
        r = respuesta()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.consciente = False  # type: ignore[misc]

    def test_acepta_los_seis_campos_del_srs(self, respuesta) -> None:
        r = respuesta(sangrado=NivelSangrado.MODERADO)
        # Si el dataclass cambia su signatura los tests del árbol se rompen
        # solos; este test ancla el contrato explícito.
        assert r.sangrado is NivelSangrado.MODERADO
        for campo in (
            "consciente",
            "respira_normal",
            "sangrado",
            "dolor_toracico",
            "dificultad_respiratoria",
            "grupo_etario",
        ):
            assert hasattr(r, campo)
