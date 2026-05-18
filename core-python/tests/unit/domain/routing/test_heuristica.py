"""Tests de haversine_m y haversine_segundos."""

from __future__ import annotations

import pytest

from sentinel_dispatch.domain.routing.heuristica import (
    V_MAX_MS,
    haversine_m,
    haversine_segundos,
)

pytestmark = pytest.mark.unit

# Coordenadas de referencia en la IV Región
_LA_SERENA = (-29.9027, -71.2519)
_COQUIMBO = (-29.9666, -71.3418)

# Distancia La Serena ↔ Coquimbo (referencia aproximada de Google Maps ~11 km)
_DIST_LS_CQ_M = 11_204.06  # metros calculados por Haversine


def test_haversine_m_la_serena_coquimbo_aprox_11km() -> None:
    """La Serena-Coquimbo es ~11.2 km; tolerancia ±5% frente al valor de referencia."""
    dist = haversine_m(*_LA_SERENA, *_COQUIMBO)
    assert dist == pytest.approx(_DIST_LS_CQ_M, rel=0.05)


def test_haversine_m_mismo_punto_es_cero() -> None:
    """La distancia de un punto a sí mismo es 0.0."""
    lat, lon = _LA_SERENA
    assert haversine_m(lat, lon, lat, lon) == 0.0


def test_haversine_m_es_simetrica() -> None:
    """haversine_m(a, b) == haversine_m(b, a) para cualquier par."""
    d_ab = haversine_m(*_LA_SERENA, *_COQUIMBO)
    d_ba = haversine_m(*_COQUIMBO, *_LA_SERENA)
    assert d_ab == pytest.approx(d_ba, rel=1e-9)


def test_haversine_segundos_igual_a_distancia_sobre_vmax() -> None:
    """haversine_segundos == haversine_m / V_MAX_MS por construcción."""
    lat1, lon1 = _LA_SERENA
    lat2, lon2 = _COQUIMBO
    dist_m = haversine_m(lat1, lon1, lat2, lon2)
    esperado = dist_m / V_MAX_MS
    assert haversine_segundos(lat1, lon1, lat2, lon2) == pytest.approx(esperado, rel=0.001)


@pytest.mark.parametrize(
    ("lat1", "lon1", "lat2", "lon2", "esperado_s"),
    [
        # mismo punto -> 0 s
        (-29.9027, -71.2519, -29.9027, -71.2519, 0.0),
        # La Serena ↔ Coquimbo
        (*_LA_SERENA, *_COQUIMBO, _DIST_LS_CQ_M / V_MAX_MS),
    ],
)
def test_haversine_segundos_valores_concretos(
    lat1: float, lon1: float, lat2: float, lon2: float, esperado_s: float
) -> None:
    """haversine_segundos retorna el valor numérico esperado para coordenadas dadas."""
    resultado = haversine_segundos(lat1, lon1, lat2, lon2)
    assert resultado == pytest.approx(esperado_s, rel=0.001, abs=1e-9)
