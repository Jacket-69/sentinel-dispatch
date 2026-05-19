"""Módulo de dispatch — función de costo, selección, re-despacho, saturación.

API pública del módulo. PR #8 entrega los tipos (entities + value objects)
y la función de costo. Los componentes restantes (selección, re-despacho,
saturación) llegan en PRs siguientes del hito H3.

Fuentes normativas:
- SRS sec. 2.6-C (función de costo) y tabla 2.6-C-1 (penalización idoneidad).
- SRS sec. 2.7 (reglas de negocio RN-01..RN-10, especialmente RN-02 / RN-04).
- ADR-0014 (ubicación de la fórmula del costo y separación dominio /
  fallback RN-02).
"""

from sentinel_dispatch.domain.dispatch.funcion_costo import (
    ALPHA,
    BETA_S,
    TABLA_PENALIZACION_IDONEIDAD,
    TViajeInvalidoError,
    UnidadInelegibleError,
    costo,
    penalizacion_idoneidad,
)
from sentinel_dispatch.domain.dispatch.redespacho import (
    UMBRAL_PROGRESO_MAXIMO,
    PropuestaRedespacho,
    evaluar_redespacho,
)
from sentinel_dispatch.domain.dispatch.seleccion import (
    CandidatoDespacho,
    ResultadoSeleccion,
    hay_cobertura_alternativa,
    seleccionar_unidad,
)
from sentinel_dispatch.domain.dispatch.tipos import (
    CostoDespacho,
    EstadoUnidad,
    Incidente,
    TipoUnidad,
    Unidad,
)

__all__ = [
    "ALPHA",
    "BETA_S",
    "TABLA_PENALIZACION_IDONEIDAD",
    "UMBRAL_PROGRESO_MAXIMO",
    "CandidatoDespacho",
    "CostoDespacho",
    "EstadoUnidad",
    "Incidente",
    "PropuestaRedespacho",
    "ResultadoSeleccion",
    "TViajeInvalidoError",
    "TipoUnidad",
    "Unidad",
    "UnidadInelegibleError",
    "costo",
    "evaluar_redespacho",
    "hay_cobertura_alternativa",
    "penalizacion_idoneidad",
    "seleccionar_unidad",
]
