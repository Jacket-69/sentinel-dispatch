"""Capa de aplicación — orquestación, política operativa, saturación.

API pública del módulo. PR #10 entrega el orquestador
:func:`despachar`, el detector de saturación :func:`detectar_saturacion`
y los value objects que combinan los resultados de las piezas de
dominio.

Fuente normativa:
- SRS sec. 2.5 (flujo principal), 2.6-D/E, 2.7 RN-02 / RN-04 / RN-08.
- ADR-0014 (función de costo del dominio).
- ADR-0015 (separación dominio/política operativa, fallback RN-02).
"""

from sentinel_dispatch.application.despachar_ambulancia import despachar
from sentinel_dispatch.application.saturacion import detectar_saturacion
from sentinel_dispatch.application.tipos import (
    CandidataRedireccion,
    EstadoSaturacion,
    MotivoDespacho,
    ResultadoDespacho,
)

__all__ = [
    "CandidataRedireccion",
    "EstadoSaturacion",
    "MotivoDespacho",
    "ResultadoDespacho",
    "despachar",
    "detectar_saturacion",
]
