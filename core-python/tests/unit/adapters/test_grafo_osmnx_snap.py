"""Tests UT del snap de `OsmnxGrafoVial` (RN-09 — SRS sec. 2.7).

Cubre `nodo_mas_cercano` y `distancia_snap_m`. Taxonomía Normal / Borde /
Error / Regla de Negocio, según la pauta de la Segunda Evaluación
(`docs/quality/trazabilidad.md` §5).
"""

from __future__ import annotations

import pytest

from sentinel_dispatch.adapters.grafo_osmnx import OsmnxGrafoVial
from sentinel_dispatch.domain.routing.tipos import NodoFueraDeRangoError

# ---------------------------------------------------------------------------
# Normal — camino feliz del snap
# ---------------------------------------------------------------------------


class TestSnapNormal:
    def test_coordenada_exacta_de_nodo_devuelve_ese_nodo(
        self, adapter_sintetico: OsmnxGrafoVial
    ) -> None:
        """Si la coord coincide con un nodo OSM, snap lo retorna."""
        nodo = adapter_sintetico.nodo_mas_cercano(-29.9077, -71.2535)
        assert nodo == 1

    def test_coordenada_intermedia_devuelve_el_nodo_mas_cercano(
        self, adapter_sintetico: OsmnxGrafoVial
    ) -> None:
        """Coord entre dos bases La Serena → snap al más cercano de los 4 nodos."""
        # Punto a mitad de camino aproximada entre nodos 1 y 2 (La Serena urbana).
        nodo = adapter_sintetico.nodo_mas_cercano(-29.9050, -71.2480)
        assert nodo in {1, 2}, "debe snapear a un nodo de La Serena, no de Coquimbo"

    def test_coordenada_cerca_de_tierras_blancas_devuelve_nodo_4(
        self, adapter_sintetico: OsmnxGrafoVial
    ) -> None:
        """Coord en Coquimbo sur → snap a Tierras Blancas (nodo 4)."""
        nodo = adapter_sintetico.nodo_mas_cercano(-29.9625, -71.3200)
        assert nodo == 4


# ---------------------------------------------------------------------------
# Borde — límites exactos del rango IV Región (RN-01 vinculada)
# ---------------------------------------------------------------------------


class TestSnapBorde:
    def test_latitud_en_limite_inferior_no_lanza(self, adapter_sintetico: OsmnxGrafoVial) -> None:
        """``lat = -30.5`` está dentro del rango cerrado."""
        nodo = adapter_sintetico.nodo_mas_cercano(-30.5, -71.30)
        assert nodo in {1, 2, 3, 4}

    def test_longitud_en_limite_superior_no_lanza(self, adapter_sintetico: OsmnxGrafoVial) -> None:
        """``lon = -70.5`` está dentro del rango cerrado."""
        nodo = adapter_sintetico.nodo_mas_cercano(-29.95, -70.5)
        assert nodo in {1, 2, 3, 4}


# ---------------------------------------------------------------------------
# Error — coordenadas inválidas o grafo degenerado
# ---------------------------------------------------------------------------


class TestSnapError:
    def test_latitud_fuera_de_rango_inferior_lanza(self, adapter_sintetico: OsmnxGrafoVial) -> None:
        """``lat = -31.0`` < ``LAT_MIN = -30.5`` → NodoFueraDeRangoError."""
        with pytest.raises(NodoFueraDeRangoError, match="cobertura"):
            adapter_sintetico.nodo_mas_cercano(-31.0, -71.30)

    def test_longitud_fuera_de_rango_superior_lanza(
        self, adapter_sintetico: OsmnxGrafoVial
    ) -> None:
        """``lon = -70.0`` > ``LON_MAX = -70.5`` → NodoFueraDeRangoError."""
        with pytest.raises(NodoFueraDeRangoError, match="cobertura"):
            adapter_sintetico.nodo_mas_cercano(-29.95, -70.0)

    def test_grafo_sin_nodos_lanza(self, grafo_vacio: object) -> None:
        """Snap sobre grafo vacío debe fallar con el mismo tipo de error."""
        import networkx as nx

        assert isinstance(grafo_vacio, nx.MultiDiGraph)
        adapter_vacio = OsmnxGrafoVial(grafo=grafo_vacio)
        with pytest.raises(NodoFueraDeRangoError, match="no contiene nodos"):
            adapter_vacio.nodo_mas_cercano(-29.9077, -71.2535)


# ---------------------------------------------------------------------------
# Regla de Negocio — RN-09 (alerta si snap > 500 m, SRS sec. 2.7)
# ---------------------------------------------------------------------------


class TestSnapReglaDeNegocio:
    def test_distancia_snap_exacto_es_cero(self, adapter_sintetico: OsmnxGrafoVial) -> None:
        """Coord que coincide con nodo → distancia_snap_m = 0.0 (≤ 1 m por float)."""
        d = adapter_sintetico.distancia_snap_m(-29.9077, -71.2535, 1)
        assert d == pytest.approx(0.0, abs=1.0)

    def test_distancia_snap_dentro_de_500m_es_aceptable_para_rn09(
        self, adapter_sintetico: OsmnxGrafoVial
    ) -> None:
        """Coord a ~50 m del nodo → distancia_snap_m < 500 m (sin alerta RN-09)."""
        # ~0.0005° lat ≈ 55 m en la latitud de La Serena.
        d = adapter_sintetico.distancia_snap_m(-29.9082, -71.2535, 1)
        assert 30.0 < d < 500.0, "snap urbano debe estar bajo el umbral RN-09"

    def test_distancia_snap_mayor_a_500m_activa_alerta_rn09(
        self, adapter_sintetico: OsmnxGrafoVial
    ) -> None:
        """Coord muy lejana del nodo (~5 km) → distancia_snap_m > 500 m (alerta RN-09).

        El adapter no emite la alerta (vive en interfaces/cli|api); este test
        verifica que la métrica supera el umbral para que el borde la dispare.
        """
        # ~0.045° lat ≈ 5 km al norte del nodo 1.
        d = adapter_sintetico.distancia_snap_m(-29.86, -71.2535, 1)
        assert d > 500.0, f"snap a 5 km debe superar el umbral RN-09, got {d:.0f} m"
