"""Módulo de incidente — entidades y validaciones del dominio de incidentes.

API pública del módulo. La validación de coordenadas de la IV Región
(RF-01 / RN-01 del SRS) vive en :mod:`validacion`. Fundamento normativo:
SRS sec. 2.13 (CP-09), ADR-0012 (ubicación del validador en dominio).
"""

from sentinel_dispatch.domain.incidente.validacion import (
    LAT_MAX_IV_REGION,
    LAT_MIN_IV_REGION,
    LON_MAX_IV_REGION,
    LON_MIN_IV_REGION,
    CoordenadasFueraDeRangoError,
    validar_coordenadas_iv_region,
)

__all__ = [
    "LAT_MAX_IV_REGION",
    "LAT_MIN_IV_REGION",
    "LON_MAX_IV_REGION",
    "LON_MIN_IV_REGION",
    "CoordenadasFueraDeRangoError",
    "validar_coordenadas_iv_region",
]
