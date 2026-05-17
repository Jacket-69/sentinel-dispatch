"""Fixtures compartidas por los tests del módulo de triaje."""

from __future__ import annotations

from typing import Any, Protocol

import pytest

from sentinel_dispatch.domain.triaje import (
    GrupoEtario,
    NivelDolorToracico,
    NivelSangrado,
    RespuestaTriaje,
)


class _RespuestaFactory(Protocol):
    def __call__(self, **overrides: Any) -> RespuestaTriaje: ...


@pytest.fixture
def respuesta() -> _RespuestaFactory:
    """Factory para construir una :class:`RespuestaTriaje` con defaults seguros.

    Los defaults representan a un paciente consciente sin Chief Complaint
    activado (equivalente operacional a "Key Questions no preguntadas" en
    MPDS real). Sobreescribir solo los campos relevantes a cada test::

        def test_x(respuesta):
            r = respuesta(consciente=False, respira_normal=False)
            ...
    """

    def _factory(**overrides: Any) -> RespuestaTriaje:
        defaults: dict[str, Any] = {
            "consciente": True,
            "respira_normal": True,
            "sangrado": NivelSangrado.NINGUNO,
            "dolor_toracico": NivelDolorToracico.NINGUNO,
            "dificultad_respiratoria": False,
            "grupo_etario": GrupoEtario.ADULTO,
        }
        defaults.update(overrides)
        return RespuestaTriaje(**defaults)

    return _factory
