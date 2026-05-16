"""Módulo de triaje — árbol MPDS-subset.

API pública del módulo. Para detalle del árbol ver :mod:`arbol`.
"""

from sentinel_dispatch.domain.triaje.arbol import clasificar_mpds
from sentinel_dispatch.domain.triaje.tipos import (
    CategoriaMPDS,
    GrupoEtario,
    RespuestaTriaje,
)

__all__ = [
    "CategoriaMPDS",
    "GrupoEtario",
    "RespuestaTriaje",
    "clasificar_mpds",
]
