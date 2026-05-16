"""Tipos del dominio de triaje.

Define las categorías MPDS, los grupos etarios y la estructura de respuesta del
árbol de triaje. Todo es lógica pura: no importa frameworks ni I/O.

Fuente normativa: SRS sec. 2.5 (entradas del operador) y sec. 2.6-A (árbol
MPDS-subset). El árbol mismo vive en :mod:`arbol`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CategoriaMPDS(str, Enum):
    """Categorías del subset MPDS aplicado por Sentinel-Dispatch.

    Orden estricto de criticidad creciente: Alpha < Bravo < Charlie < Delta < Echo.
    Comparable mediante :meth:`__lt__` por el orden de declaración.

    Referencia: SRS sec. 2.6-A.
    """

    ALPHA = "Alpha"
    BRAVO = "Bravo"
    CHARLIE = "Charlie"
    DELTA = "Delta"
    ECHO = "Echo"

    def __lt__(self, other: object) -> bool:  # noqa: D401
        if not isinstance(other, CategoriaMPDS):
            return NotImplemented
        order = list(CategoriaMPDS)
        return order.index(self) < order.index(other)


class GrupoEtario(str, Enum):
    """Grupos etarios reconocidos por el árbol de triaje.

    Referencia: SRS sec. 2.5 (entradas del operador, variable Grupo etario).
    """

    PEDIATRICO = "Pediátrico"
    ADULTO = "Adulto"
    ANCIANO = "Anciano"


@dataclass(frozen=True, slots=True)
class RespuestaTriaje:
    """Respuestas del operador al árbol MPDS-subset.

    Inmutable. Validar consistencia de campos al construir es responsabilidad
    del adapter de entrada (interfaces/cli o interfaces/api), no del dominio.

    Atributos según SRS sec. 2.5:

    - ``consciente``: ¿el paciente está consciente?
    - ``respira``: ¿respira con normalidad? Solo se evalúa si ``consciente``;
      sin embargo, el dataclass acepta el valor siempre para mantener forma
      uniforme (el árbol decide cuándo se usa).
    - ``sangrado_activo``: ¿hay sangrado activo visible?
    - ``dolor_toracico``: ¿dolor torácico o dificultad respiratoria severa?
    - ``dificultad_respiratoria``: ¿dificultad respiratoria moderada?
    - ``grupo_etario``: pediátrico, adulto o anciano.
    """

    consciente: bool
    respira: bool
    sangrado_activo: bool
    dolor_toracico: bool
    dificultad_respiratoria: bool
    grupo_etario: GrupoEtario
