"""UT del `factor_calibracion` en `cargar_grafo_iv_region` (ADR-0013 §H4-cal-1)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from sentinel_dispatch.adapters.grafo_osmnx import (
    MAXSPEED_FALLBACK_KMH,
    _aplicar_factor_calibracion,
)

if TYPE_CHECKING:
    import networkx as nx


class TestAplicarFactorCalibracion:
    def test_factor_0_85_escala_speed_kph_inplace(
        self, grafo_iv_region_sintetico: nx.MultiDiGraph
    ) -> None:
        """factor=0.85 → speed_kph original × 0.85 en cada arista."""
        speeds_originales = [
            data["speed_kph"] for _u, _v, data in grafo_iv_region_sintetico.edges(data=True)
        ]
        _aplicar_factor_calibracion(grafo_iv_region_sintetico, 0.85)
        speeds_post = [
            data["speed_kph"] for _u, _v, data in grafo_iv_region_sintetico.edges(data=True)
        ]
        assert speeds_post == pytest.approx([s * 0.85 for s in speeds_originales])

    def test_factor_1_0_es_identidad(self, grafo_iv_region_sintetico: nx.MultiDiGraph) -> None:
        speeds_originales = [
            data["speed_kph"] for _u, _v, data in grafo_iv_region_sintetico.edges(data=True)
        ]
        _aplicar_factor_calibracion(grafo_iv_region_sintetico, 1.0)
        speeds_post = [
            data["speed_kph"] for _u, _v, data in grafo_iv_region_sintetico.edges(data=True)
        ]
        assert speeds_post == speeds_originales

    def test_arista_sin_speed_kph_usa_fallback(
        self, grafo_iv_region_sintetico: nx.MultiDiGraph
    ) -> None:
        """Si una arista carece de speed_kph, usa MAXSPEED_FALLBACK_KMH × factor."""
        # Borrar el atributo de una arista para simular el caso degenerado.
        u, v, _key = next(iter(grafo_iv_region_sintetico.edges(keys=True)))
        del grafo_iv_region_sintetico[u][v][0]["speed_kph"]

        _aplicar_factor_calibracion(grafo_iv_region_sintetico, 0.5)
        nueva = grafo_iv_region_sintetico[u][v][0]["speed_kph"]
        assert nueva == pytest.approx(MAXSPEED_FALLBACK_KMH * 0.5)


class TestCargarGrafoConFactor:
    def test_factor_calibracion_negativo_lanza_value_error(self, tmp_path: object) -> None:
        from sentinel_dispatch.adapters.grafo_osmnx import cargar_grafo_iv_region

        with pytest.raises(ValueError, match="factor_calibracion"):
            cargar_grafo_iv_region(factor_calibracion=-0.1)

    def test_factor_calibracion_cero_lanza_value_error(self) -> None:
        from sentinel_dispatch.adapters.grafo_osmnx import cargar_grafo_iv_region

        with pytest.raises(ValueError, match="factor_calibracion"):
            cargar_grafo_iv_region(factor_calibracion=0.0)
