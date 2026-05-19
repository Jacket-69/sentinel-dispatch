"""Tests UT de ``validar_coordenadas_iv_region`` (RF-01 / RN-01 — SRS sec. 2.6).

Cubre la función pura del dominio y la excepción
:class:`CoordenadasFueraDeRangoError`. Taxonomía Normal / Borde / Error /
Regla de Negocio, según la pauta de la Segunda Evaluación
(``docs/quality/trazabilidad.md`` §5).

CP-09 (SRS sec. 2.13) está cubierto por el test marcado con
``# CP-09`` en :class:`TestValidacionReglaDeNegocio`.
"""

from __future__ import annotations

import math

import pytest

from sentinel_dispatch.domain.incidente.validacion import (
    LAT_MAX_IV_REGION,
    LAT_MIN_IV_REGION,
    LON_MAX_IV_REGION,
    LON_MIN_IV_REGION,
    MENSAJE_FUERA_DE_RANGO,
    CoordenadasFueraDeRangoError,
    validar_coordenadas_iv_region,
)

# ---------------------------------------------------------------------------
# Normal — coordenadas claramente dentro del bbox IV Región
# ---------------------------------------------------------------------------


class TestValidacionNormal:
    def test_coquimbo_centro_no_lanza(self) -> None:
        """Centro de Coquimbo (-29.95, -71.34) es válido."""
        validar_coordenadas_iv_region(-29.95, -71.34)

    def test_la_serena_centro_no_lanza(self) -> None:
        """Centro de La Serena (-29.9077, -71.2535) es válido."""
        validar_coordenadas_iv_region(-29.9077, -71.2535)

    def test_ovalle_no_lanza(self) -> None:
        """Ovalle (-30.6, -71.2) — fuera de rango (lat < -30.5).

        Pendiente del SRS: Ovalle queda fuera del bbox normativo H1.
        Se documenta aquí como ejemplo intencional para que un revisor
        no se sorprenda. La validación rechaza.
        """
        with pytest.raises(CoordenadasFueraDeRangoError):
            validar_coordenadas_iv_region(-30.6, -71.2)


# ---------------------------------------------------------------------------
# Borde — límites exactos del rango cerrado
# ---------------------------------------------------------------------------


class TestValidacionBorde:
    def test_latitud_en_limite_inferior_no_lanza(self) -> None:
        """``lat = LAT_MIN_IV_REGION`` (-30.5) está dentro del rango cerrado."""
        validar_coordenadas_iv_region(LAT_MIN_IV_REGION, -71.0)

    def test_latitud_en_limite_superior_no_lanza(self) -> None:
        """``lat = LAT_MAX_IV_REGION`` (-29.5) está dentro del rango cerrado."""
        validar_coordenadas_iv_region(LAT_MAX_IV_REGION, -71.0)

    def test_longitud_en_limite_inferior_no_lanza(self) -> None:
        """``lon = LON_MIN_IV_REGION`` (-71.7) está dentro del rango cerrado."""
        validar_coordenadas_iv_region(-30.0, LON_MIN_IV_REGION)

    def test_longitud_en_limite_superior_no_lanza(self) -> None:
        """``lon = LON_MAX_IV_REGION`` (-70.5) está dentro del rango cerrado."""
        validar_coordenadas_iv_region(-30.0, LON_MAX_IV_REGION)


# ---------------------------------------------------------------------------
# Error — coordenadas inválidas (fuera de rango o no-finitas)
# ---------------------------------------------------------------------------


class TestValidacionError:
    def test_latitud_fuera_de_rango_inferior_lanza(self) -> None:
        """``lat = -31.0`` < ``LAT_MIN`` → rechazo."""
        with pytest.raises(CoordenadasFueraDeRangoError) as exc_info:
            validar_coordenadas_iv_region(-31.0, -71.0)
        assert exc_info.value.lat == -31.0
        assert exc_info.value.lon == -71.0

    def test_longitud_fuera_de_rango_superior_lanza(self) -> None:
        """``lon = -70.0`` > ``LON_MAX`` → rechazo."""
        with pytest.raises(CoordenadasFueraDeRangoError):
            validar_coordenadas_iv_region(-29.95, -70.0)

    def test_nan_en_latitud_lanza(self) -> None:
        """``lat = NaN`` debe rechazarse antes del chequeo de rango."""
        with pytest.raises(CoordenadasFueraDeRangoError):
            validar_coordenadas_iv_region(math.nan, -71.0)

    def test_infinito_en_longitud_lanza(self) -> None:
        """``lon = +inf`` debe rechazarse antes del chequeo de rango."""
        with pytest.raises(CoordenadasFueraDeRangoError):
            validar_coordenadas_iv_region(-30.0, math.inf)


# ---------------------------------------------------------------------------
# Regla de Negocio — RN-01 (rango IV Región) y CP-09 textual
# ---------------------------------------------------------------------------


class TestValidacionReglaDeNegocio:
    def test_cp09_textual_lat_minus_31_2_lon_minus_71_3(self) -> None:
        """CP-09 (SRS sec. 2.13): ``lat=-31.2, lon=-71.3`` se rechaza con el
        mensaje normativo "Coordenadas fuera del área de cobertura (IV
        Región)." y los atributos ``lat``/``lon`` preservan los valores
        originales para logging estructurado.
        """
        with pytest.raises(CoordenadasFueraDeRangoError) as exc_info:
            validar_coordenadas_iv_region(-31.2, -71.3)
        assert str(exc_info.value) == MENSAJE_FUERA_DE_RANGO
        assert exc_info.value.lat == -31.2
        assert exc_info.value.lon == -71.3

    def test_excepcion_es_subclase_de_value_error(self) -> None:
        """``CoordenadasFueraDeRangoError`` hereda de ``ValueError`` para
        que handlers genéricos del borde (API/CLI) la capturen como
        violación de input en vez de error técnico.
        """
        with pytest.raises(ValueError, match="cobertura"):
            validar_coordenadas_iv_region(-31.2, -71.3)
