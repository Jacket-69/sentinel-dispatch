"""Tests de :func:`proyectar_en_polilinea` (snap-to-edge, ADR-0020 §3a).

Lógica geométrica pura: sin OSMnx ni grafo real. Verifica la fracción a lo
largo de la polilínea, el punto proyectado y la distancia de snap en metros,
en el plano métrico local.
"""

from __future__ import annotations

import pytest

from sentinel_dispatch.domain.routing.geometria import (
    METROS_POR_GRADO_LAT,
    proyectar_en_polilinea,
)

# Recta este-oeste a latitud constante (lon crece hacia el este).
_A = (-29.9000, -71.2500)
_B = (-29.9000, -71.2400)


def test_proyeccion_al_medio_de_un_segmento() -> None:
    # Punto al sur del punto medio (mismo lon medio): fracción ~0.5.
    fraccion, lat_p, lon_p, dist = proyectar_en_polilinea(-29.9010, -71.2450, [_A, _B])
    assert fraccion == pytest.approx(0.5, abs=0.01)
    assert lat_p == pytest.approx(-29.9000, abs=1e-4)
    assert lon_p == pytest.approx(-71.2450, abs=1e-4)
    # Δlat de 0.0010° ≈ 111.3 m de distancia perpendicular.
    assert dist == pytest.approx(0.0010 * METROS_POR_GRADO_LAT, rel=0.02)


def test_proyeccion_sobre_un_vertice_exacto() -> None:
    fraccion, lat_p, lon_p, dist = proyectar_en_polilinea(_A[0], _A[1], [_A, _B])
    assert fraccion == pytest.approx(0.0, abs=1e-6)
    assert lat_p == pytest.approx(_A[0])
    assert lon_p == pytest.approx(_A[1])
    assert dist == pytest.approx(0.0, abs=1e-6)


def test_proyeccion_mas_alla_del_extremo_hace_clamp() -> None:
    # Punto al oeste del extremo A: la proyección se satura en A (fracción 0).
    fraccion, lat_p, lon_p, _dist = proyectar_en_polilinea(-29.9000, -71.2600, [_A, _B])
    assert fraccion == pytest.approx(0.0, abs=1e-6)
    assert lat_p == pytest.approx(_A[0])
    assert lon_p == pytest.approx(_A[1])


def test_proyeccion_mas_alla_del_extremo_destino_hace_clamp() -> None:
    fraccion, lat_p, lon_p, _dist = proyectar_en_polilinea(-29.9000, -71.2300, [_A, _B])
    assert fraccion == pytest.approx(1.0, abs=1e-6)
    assert lat_p == pytest.approx(_B[0])
    assert lon_p == pytest.approx(_B[1])


def test_polilinea_de_un_solo_punto() -> None:
    fraccion, lat_p, lon_p, dist = proyectar_en_polilinea(-29.9010, -71.2500, [_A])
    assert fraccion == 0.0
    assert (lat_p, lon_p) == _A
    assert dist == pytest.approx(0.0010 * METROS_POR_GRADO_LAT, rel=0.02)


def test_proyeccion_sobre_polilinea_en_codo() -> None:
    # Polilínea en "L": A → B (este) → C (sur de B).
    c = (-29.9100, -71.2400)
    # Punto cerca del codo B: debe proyectar muy cerca de B, fracción ~0.5.
    fraccion, lat_p, lon_p, dist = proyectar_en_polilinea(
        -29.9001, -71.2401, [_A, _B, c]
    )
    assert 0.45 <= fraccion <= 0.55
    assert lat_p == pytest.approx(_B[0], abs=1e-3)
    assert lon_p == pytest.approx(_B[1], abs=1e-3)
    assert dist < 20.0


def test_polilinea_vacia_es_error() -> None:
    with pytest.raises(ValueError, match="al menos un vértice"):
        proyectar_en_polilinea(-29.9000, -71.2500, [])
