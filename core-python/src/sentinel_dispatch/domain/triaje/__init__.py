"""Módulo de triaje — árbol MPDS-subset.

API pública del módulo. Para detalle del árbol y mapeo MPDS ver :mod:`arbol`
y la sub-sección 2.6-A.1 del SRS.
"""

from sentinel_dispatch.domain.triaje.arbol import clasificar_mpds
from sentinel_dispatch.domain.triaje.tipos import (
    CategoriaMPDS,
    GrupoEtario,
    NivelDolorToracico,
    NivelSangrado,
    RespuestaTriaje,
)

__all__ = [
    "CategoriaMPDS",
    "GrupoEtario",
    "NivelDolorToracico",
    "NivelSangrado",
    "RespuestaTriaje",
    "clasificar_mpds",
]
