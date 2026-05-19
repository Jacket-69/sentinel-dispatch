"""Validación de coordenadas del incidente — RF-01 / RN-01 del SRS.

Aplica el rango geográfico de la IV Región de Coquimbo a un par
``(lat, lon)`` antes de cualquier cálculo (snap, A*, despacho). La función
:func:`validar_coordenadas_iv_region` es invocada en el borde por
``interfaces/api`` y ``interfaces/cli`` (RF-01) y reutilizada como red de
seguridad por el adapter ``OsmnxGrafoVial.nodo_mas_cercano`` (RN-09).

Fuente normativa:
- SRS sec. 2.6 (RN-01 — Validación de rango).
- SRS sec. 2.13 — CP-09: ``lat = -31.200000, lon = -71.300000`` rechazado
  con mensaje ``"Coordenadas fuera del área de cobertura (IV Región)"`` y
  sin generar log de despacho.
- ADR-0012: ubicación del validador en dominio (no en adapter).
"""

from __future__ import annotations

import math

LAT_MIN_IV_REGION: float = -30.5
"""Latitud mínima inclusiva del bbox normativo IV Región (SRS RN-01)."""

LAT_MAX_IV_REGION: float = -29.5
"""Latitud máxima inclusiva del bbox normativo IV Región (SRS RN-01)."""

LON_MIN_IV_REGION: float = -71.7
"""Longitud mínima inclusiva del bbox normativo IV Región (SRS RN-01)."""

LON_MAX_IV_REGION: float = -70.5
"""Longitud máxima inclusiva del bbox normativo IV Región (SRS RN-01)."""

MENSAJE_FUERA_DE_RANGO: str = "Coordenadas fuera del área de cobertura (IV Región)."
"""Mensaje textual exigido por CP-09 del SRS sec. 2.13."""


class CoordenadasFueraDeRangoError(ValueError):
    """RN-01 — coordenadas fuera del área de cobertura de la IV Región.

    Hereda de :class:`ValueError` porque semánticamente es un valor de
    entrada inválido en el borde del sistema. Captura los datos crudos
    en :attr:`lat` y :attr:`lon` para facilitar logging estructurado.
    """

    def __init__(self, lat: float, lon: float, mensaje: str = MENSAJE_FUERA_DE_RANGO) -> None:
        self.lat = lat
        self.lon = lon
        super().__init__(mensaje)


def validar_coordenadas_iv_region(lat: float, lon: float) -> None:
    """Valida que ``(lat, lon)`` caiga dentro del bbox IV Región (RN-01).

    Args:
        lat: latitud en EPSG:4326 (grados decimales).
        lon: longitud en EPSG:4326 (grados decimales).

    Raises:
        CoordenadasFueraDeRangoError: si ``lat`` o ``lon`` están fuera del
            rango cerrado ``[LAT_MIN_IV_REGION, LAT_MAX_IV_REGION]`` por
            ``[LON_MIN_IV_REGION, LON_MAX_IV_REGION]``, o si alguno de los
            dos no es finito (``NaN`` o ``±inf``).

    El rango es cerrado en ambos extremos: los límites exactos se aceptan
    como válidos. La verificación de finitud va primero porque
    ``math.nan`` no satisface ningún operador de orden y burlaría el
    chequeo de rango por puro accidente del IEEE-754.
    """
    if not math.isfinite(lat) or not math.isfinite(lon):
        raise CoordenadasFueraDeRangoError(lat, lon)
    if not (LAT_MIN_IV_REGION <= lat <= LAT_MAX_IV_REGION):
        raise CoordenadasFueraDeRangoError(lat, lon)
    if not (LON_MIN_IV_REGION <= lon <= LON_MAX_IV_REGION):
        raise CoordenadasFueraDeRangoError(lat, lon)
