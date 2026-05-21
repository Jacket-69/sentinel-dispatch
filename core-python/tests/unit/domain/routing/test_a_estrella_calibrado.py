"""UT del A* calibrado experimental (ADR-0013 §H4-cal-2)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from sentinel_dispatch.domain.routing.a_estrella_calibrado import (
    _bearing_grados,
    _delta_bearing,
    a_estrella_calibrado,
)
from sentinel_dispatch.domain.routing.tipos import Arista, NoRutaDisponibleError

if TYPE_CHECKING:
    from collections.abc import Iterable


# ---------------------------------------------------------------------------
# Fake grafo lineal para tests
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _FakeGrafo:
    """Grafo trivial: aristas y coords explícitas."""

    aristas_por_nodo: dict[int, list[Arista]]
    coords_por_nodo: dict[int, tuple[float, float]]

    def vecinos(self, nodo: int) -> Iterable[Arista]:
        return self.aristas_por_nodo.get(nodo, [])

    def coordenadas(self, nodo: int) -> tuple[float, float]:
        return self.coords_por_nodo[nodo]

    def nodo_mas_cercano(self, lat: float, lon: float) -> int:  # pragma: no cover
        return 0

    def distancia_snap_m(self, lat: float, lon: float, nodo: int) -> float:  # pragma: no cover
        return 0.0


def _arista(origen: int, destino: int, longitud_m: float, kmh: float = 36.0) -> Arista:
    return Arista(
        origen=origen,
        destino=destino,
        longitud_m=longitud_m,
        velocidad_efectiva_kmh=kmh,
    )


# ---------------------------------------------------------------------------
# _bearing_grados / _delta_bearing
# ---------------------------------------------------------------------------


class TestBearing:
    def test_bearing_norte_es_cero(self) -> None:
        b = _bearing_grados(0.0, 0.0, 1.0, 0.0)
        assert b == pytest.approx(0.0, abs=0.5)

    def test_bearing_este_es_90(self) -> None:
        b = _bearing_grados(0.0, 0.0, 0.0, 1.0)
        assert b == pytest.approx(90.0, abs=0.5)

    def test_delta_bearing_es_simetrico(self) -> None:
        assert _delta_bearing(10.0, 350.0) == pytest.approx(20.0)
        assert _delta_bearing(350.0, 10.0) == pytest.approx(20.0)

    def test_delta_bearing_max_es_180(self) -> None:
        assert _delta_bearing(0.0, 180.0) == pytest.approx(180.0)


# ---------------------------------------------------------------------------
# A* calibrado vs sin penalty
# ---------------------------------------------------------------------------


class TestAEstrellaCalibrado:
    def test_ruta_recta_sin_penalty_devuelve_eta_simple(self) -> None:
        """Ruta 1→2→3 hacia el este: sin giros, no aplica penalty."""
        # Coords: 1@(0,0), 2@(0,0.001), 3@(0,0.002). Aristas 1→2 y 2→3 de
        # 100 m a 36 km/h = 10 s cada una. Total 20 s.
        coords = {1: (0.0, 0.0), 2: (0.0, 0.001), 3: (0.0, 0.002)}
        aristas = {
            1: [_arista(1, 2, 100.0)],
            2: [_arista(2, 3, 100.0)],
            3: [],
        }
        grafo = _FakeGrafo(aristas_por_nodo=aristas, coords_por_nodo=coords)
        eta, ruta = a_estrella_calibrado(
            grafo,
            origen=1,
            destino=3,
            turn_penalty_s=2.0,
            bearing_umbral_grados=30.0,
        )
        assert ruta == [1, 2, 3]
        assert eta == pytest.approx(20.0, abs=0.5)

    def test_giro_90_grados_aplica_turn_penalty(self) -> None:
        """Ruta 1→2→3 con giro de 90° en 2 suma turn_penalty_s al eta."""
        # Coords: 1@(0,0), 2@(0,0.001) este, 3@(0.001,0.001) norte → giro 90°.
        coords = {1: (0.0, 0.0), 2: (0.0, 0.001), 3: (0.001, 0.001)}
        aristas = {
            1: [_arista(1, 2, 100.0)],
            2: [_arista(2, 3, 100.0)],
            3: [],
        }
        grafo = _FakeGrafo(aristas_por_nodo=aristas, coords_por_nodo=coords)
        eta, ruta = a_estrella_calibrado(
            grafo,
            origen=1,
            destino=3,
            turn_penalty_s=2.0,
            bearing_umbral_grados=30.0,
        )
        assert ruta == [1, 2, 3]
        # 100/10 + 100/10 + 2.0 (penalty del giro 90°) = 22 s
        assert eta == pytest.approx(22.0, abs=0.5)

    def test_origen_igual_destino_eta_cero(self) -> None:
        coords = {1: (0.0, 0.0)}
        grafo = _FakeGrafo(aristas_por_nodo={1: []}, coords_por_nodo=coords)
        eta, ruta = a_estrella_calibrado(grafo, 1, 1)
        assert eta == 0.0
        assert ruta == [1]

    def test_sin_ruta_lanza_excepcion(self) -> None:
        coords = {1: (0.0, 0.0), 2: (0.0, 0.001)}
        grafo = _FakeGrafo(aristas_por_nodo={1: [], 2: []}, coords_por_nodo=coords)
        with pytest.raises(NoRutaDisponibleError):
            a_estrella_calibrado(grafo, 1, 2)

    def test_factor_hora_invalido_lanza_value_error(self) -> None:
        coords = {1: (0.0, 0.0), 2: (0.0, 0.001)}
        grafo = _FakeGrafo(aristas_por_nodo={1: [_arista(1, 2, 100.0)]}, coords_por_nodo=coords)
        with pytest.raises(ValueError, match="factor_hora"):
            a_estrella_calibrado(grafo, 1, 2, factor_hora=0.0)

    def test_turn_penalty_cero_equivale_al_a_star_simple(self) -> None:
        """Con turn_penalty_s=0, dos rutas con/sin giro deben dar el mismo eta."""
        coords = {1: (0.0, 0.0), 2: (0.0, 0.001), 3: (0.001, 0.001)}
        aristas = {
            1: [_arista(1, 2, 100.0)],
            2: [_arista(2, 3, 100.0)],
            3: [],
        }
        grafo = _FakeGrafo(aristas_por_nodo=aristas, coords_por_nodo=coords)
        eta, _ = a_estrella_calibrado(grafo, origen=1, destino=3, turn_penalty_s=0.0)
        assert eta == pytest.approx(20.0, abs=0.5)
