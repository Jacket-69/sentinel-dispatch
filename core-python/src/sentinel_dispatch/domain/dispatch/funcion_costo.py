"""Función de costo multiobjetivo del despacho (SRS sec. 2.6-C).

Implementa la fórmula normativa::

    Costo(u, i) = α · T_viaje(u → i) + β · Penalización_Idoneidad(u, i)

con ``α = 1.0`` (adimensional, equilibra distancia temporal) y
``β = 600 s`` (escala la penalización categórica a magnitud de
desviación operativa equivalente a 10 minutos de viaje extra).

La tabla de penalización (:data:`TABLA_PENALIZACION_IDONEIDAD`) traduce
la jerarquía MPDS × Tipo de unidad a un escalar finito + ``math.inf``
para las combinaciones prohibidas (Echo/Delta + Básica). El despacho
con flag ``despacho_suboptimo`` cuando la única Disponible es Básica
para Echo/Delta (RN-02) **no vive aquí**: es lógica de fallback de
application/, no de cálculo de costo. La separación se documenta en
ADR-0014 y se ejecuta en ADR-0015 (PR posterior).

Fuente normativa: SRS sec. 2.6-C, tabla 2.6-C-1, RN-02, RN-04.
Decisión arquitectónica: ADR-0014.
"""

from __future__ import annotations

import math
from typing import Final

from sentinel_dispatch.domain.dispatch.tipos import (
    CostoDespacho,
    EstadoUnidad,
    Incidente,
    TipoUnidad,
    Unidad,
)
from sentinel_dispatch.domain.triaje.tipos import CategoriaMPDS

ALPHA: Final[float] = 1.0
"""Peso del tiempo de viaje en la función de costo (SRS sec. 2.6-C).

Adimensional. Mantenido en 1.0 mientras no haya evidencia empírica para
recalibrarlo; cualquier cambio requiere ADR explícito.
"""

BETA_S: Final[float] = 600.0
"""Peso de la penalización de idoneidad en segundos (SRS sec. 2.6-C).

Convierte el escalar de la tabla a magnitud temporal. ``β = 600`` significa
que penalización ``1`` (Charlie + Básica) equivale a 10 minutos de viaje
extra — *como si* la unidad estuviera 10 min más lejos del incidente.
Suficiente para que una Avanzada lejana le gane a una Básica cercana en
los rangos urbanos típicos de Coquimbo (1-5 km).
"""


TABLA_PENALIZACION_IDONEIDAD: Final[dict[tuple[CategoriaMPDS, TipoUnidad], float]] = {
    (CategoriaMPDS.ECHO, TipoUnidad.AVANZADA): 0.0,
    (CategoriaMPDS.ECHO, TipoUnidad.BASICA): math.inf,
    (CategoriaMPDS.DELTA, TipoUnidad.AVANZADA): 0.0,
    (CategoriaMPDS.DELTA, TipoUnidad.BASICA): math.inf,
    (CategoriaMPDS.CHARLIE, TipoUnidad.AVANZADA): 0.0,
    (CategoriaMPDS.CHARLIE, TipoUnidad.BASICA): 1.0,
    (CategoriaMPDS.BRAVO, TipoUnidad.AVANZADA): 0.0,
    (CategoriaMPDS.BRAVO, TipoUnidad.BASICA): 0.0,
    (CategoriaMPDS.ALPHA, TipoUnidad.AVANZADA): 0.0,
    (CategoriaMPDS.ALPHA, TipoUnidad.BASICA): 0.0,
}
"""Penalización categórica por combinación MPDS × Tipo de Unidad.

Construida exhaustivamente (5 categorías × 2 tipos = 10 entradas) para
que ``penalizacion_idoneidad`` no necesite branches condicionales y para
que un revisor pueda verificar la tabla al ojo contra el SRS sec. 2.6-C.

Reglas codificadas (SRS sec. 2.6-C tabla 1):

- **Echo + Avanzada / Delta + Avanzada**: 0 (combinación ideal).
- **Echo + Básica / Delta + Básica**: ``∞`` (prohibida por idoneidad
  médica; RN-02 maneja el fallback cuando es la *única* disponible).
- **Charlie + Avanzada**: 0.
- **Charlie + Básica**: 1.0 (penalizada pero no prohibida; equivale a
  ``β · 1 = 600 s`` de viaje extra equivalente).
- **Bravo / Alpha + Avanzada / Básica**: 0 (cualquiera atiende).
"""


class UnidadInelegibleError(ValueError):
    """La unidad no puede entrar al cálculo bajo ninguna circunstancia.

    Se lanza cuando la unidad está en estado ``TALLER`` (RN-04). El
    caller debe filtrar previamente la flota o atrapar y excluir.
    Mantenida como excepción del dominio para que un olvido en el
    application layer falle ruidoso en lugar de silenciar la regla.
    """


class TViajeInvalidoError(ValueError):
    """El tiempo de viaje no es finito o es negativo.

    Casos detectados:

    - ``t_viaje_s < 0``: imposible físicamente.
    - ``t_viaje_s`` es ``NaN``: probablemente un error de A* o de
      conversión upstream; preferimos fallar antes que propagar NaN
      hasta el ``argmin``.

    ``t_viaje_s == math.inf`` se acepta como valor válido (representa
    "no hay ruta desde la base de la unidad al incidente") y resulta
    en ``CostoDespacho.es_infinito = True``.
    """


def penalizacion_idoneidad(categoria: CategoriaMPDS, tipo: TipoUnidad) -> float:
    """Devuelve la penalización categórica para la combinación dada.

    Consulta plana sobre :data:`TABLA_PENALIZACION_IDONEIDAD`. Si una
    combinación nueva se agrega a los enums sin entrada en la tabla,
    el lookup falla con ``KeyError`` ruidoso — preferible a un default
    silencioso que podría enmascarar un bug del SRS.

    Args:
        categoria: salida del árbol de triaje (Alpha..Echo).
        tipo: tipo de unidad (Avanzada o Básica).

    Returns:
        Escalar finito (0.0 o 1.0) ó ``math.inf`` para combinaciones
        prohibidas. Antes de multiplicar por :data:`BETA_S`.

    Raises:
        KeyError: si la combinación no está en la tabla (defensa
            anti-drift entre enums y tabla).
    """
    return TABLA_PENALIZACION_IDONEIDAD[(categoria, tipo)]


def costo(unidad: Unidad, incidente: Incidente, t_viaje_s: float) -> CostoDespacho:
    """Calcula ``Costo(u, i) = α · T_viaje + β · Penalización_Idoneidad``.

    No conoce el routing: ``t_viaje_s`` se recibe ya calculado por el
    caller (application/ orquesta snap → A* → costo). Esa separación
    permite probar la función con valores sintéticos sin grafo cargado
    (ADR-0014 §Decisión).

    Args:
        unidad: móvil SAMU candidato. Debe estar Disponible o EnRuta
            (re-despacho); ``TALLER`` lanza :exc:`UnidadInelegibleError`
            por RN-04.
        incidente: evento triado con categoría MPDS.
        t_viaje_s: tiempo de viaje del A* en segundos. Debe ser
            ``≥ 0`` y finito o ``math.inf``; NaN o negativo lanza
            :exc:`TViajeInvalidoError`.

    Returns:
        :class:`CostoDespacho` con desglose. ``valor_total_s`` es
        ``math.inf`` cuando la penalización es ``∞`` o cuando
        ``t_viaje_s`` es ``∞`` (sin ruta).

    Raises:
        UnidadInelegibleError: si la unidad está en ``TALLER`` (RN-04).
        TViajeInvalidoError: si ``t_viaje_s`` es NaN o negativo.
    """
    if unidad.estado is EstadoUnidad.TALLER:
        raise UnidadInelegibleError(
            f"Unidad {unidad.id} está en Taller; RN-04 la excluye del cálculo."
        )
    if math.isnan(t_viaje_s) or t_viaje_s < 0.0:
        raise TViajeInvalidoError(
            f"T_viaje={t_viaje_s!r} inválido para unidad {unidad.id} → "
            f"incidente {incidente.id}; se espera valor finito ≥ 0 o math.inf."
        )

    pen = penalizacion_idoneidad(incidente.categoria_mpds, unidad.tipo)

    if math.isinf(pen) or math.isinf(t_viaje_s):
        return CostoDespacho(
            valor_total_s=math.inf,
            t_viaje_s=t_viaje_s,
            penalizacion=pen,
            es_infinito=True,
        )

    return CostoDespacho(
        valor_total_s=ALPHA * t_viaje_s + BETA_S * pen,
        t_viaje_s=t_viaje_s,
        penalizacion=pen,
        es_infinito=False,
    )
