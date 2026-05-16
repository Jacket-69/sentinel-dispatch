"""Tipos del dominio de triaje.

Define las categorías MPDS, los grupos etarios, los niveles de sangrado y
dolor torácico, y la estructura de respuesta del árbol de triaje. Todo es
lógica pura: no importa frameworks ni I/O.

Fuente normativa: SRS sec. 2.5 (entradas del operador) y sec. 2.6-A (árbol
MPDS-subset). El árbol mismo vive en :mod:`arbol`. El mapeo a MPDS oficial
se documenta en la sub-sección 2.6-A.1 del SRS y en ADR-0009.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CategoriaMPDS(str, Enum):
    """Categorías del subset MPDS aplicado por Sentinel-Dispatch.

    Orden estricto de criticidad creciente: Alpha < Bravo < Charlie < Delta < Echo.
    Comparable mediante :meth:`__lt__` por el orden de declaración.

    Niveles MPDS oficiales (Priority Dispatch Corp):

    - **Alpha**: BLS no urgente (Básica, sin sirena).
    - **Bravo**: BLS urgente (Básica, con sirena).
    - **Charlie**: ALS no urgente (Avanzada, sin sirena).
    - **Delta**: ALS urgente (Avanzada, con sirena).
    - **Echo**: ALS + recursos múltiples (paro inminente).
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

    Referencia: SRS sec. 2.5. Reservado para subdeterminantes específicos
    (ej. Protocol 6 pediátrico). No entra al árbol v1.
    """

    PEDIATRICO = "Pediátrico"
    ADULTO = "Adulto"
    ANCIANO = "Anciano"


class NivelSangrado(str, Enum):
    """Nivel de sangrado visible.

    Mapeo a MPDS Protocol 21 (Hemorrhage/Lacerations):

    - ``NINGUNO``: sin sangrado visible. No aplica Protocol 21.
    - ``MODERADO``: sangrado uncontrolled fuera de zona peligrosa
      (≈ Protocol 21-B-2 Serious hemorrhage).
    - ``ACTIVO``: sangrado uncontrolled sin verificación de ubicación.
      Adaptación SAMU Chile (eleva a Charlie). Detalle en ADR-0009.
    - ``PELIGROSO``: sangrado arterial o en zonas críticas (axila, ingle,
      cuello) — ≈ Protocol 21-D-4 Dangerous hemorrhage.
    """

    NINGUNO = "Ninguno"
    MODERADO = "Moderado"
    ACTIVO = "Activo"
    PELIGROSO = "Peligroso"


class NivelDolorToracico(str, Enum):
    """Nivel de dolor torácico.

    Mapeo a MPDS Protocol 10 (Chest Pain):

    - ``NINGUNO``: sin dolor torácico. No aplica Protocol 10.
    - ``PRESENTE``: chest pain aislado, paciente alerta, sin síntomas
      asociados graves (≈ Protocol 10-C).
    - ``CRITICO``: chest pain con síntoma asociado severo (not alert,
      abnormal breathing, clammy, irradiación severa) — ≈ Protocol 10-D.
    """

    NINGUNO = "Ninguno"
    PRESENTE = "Presente"
    CRITICO = "Crítico"


@dataclass(frozen=True, slots=True)
class RespuestaTriaje:
    """Respuestas del operador al árbol MPDS-subset.

    Inmutable. Validar consistencia de campos al construir es responsabilidad
    del adapter de entrada (interfaces/cli o interfaces/api), no del dominio.

    Atributos según SRS sec. 2.5:

    - ``consciente``: ¿el paciente está consciente?
    - ``respira_normal``: ¿respira con normalidad? Distingue MPDS 31-D-2
      (effective breathing) de 9-E-1 / 31-E-1 (arrest / ineffective).
      Solo se evalúa cuando ``consciente=False``; el dataclass acepta el
      valor siempre por uniformidad estructural.
    - ``sangrado``: nivel de sangrado visible (ver :class:`NivelSangrado`).
    - ``dolor_toracico``: nivel de dolor torácico (ver :class:`NivelDolorToracico`).
    - ``dificultad_respiratoria``: presencia de dificultad respiratoria
      (Protocol 6 / Protocol 31-C-1).
    - ``grupo_etario``: pediátrico, adulto o anciano. Reservado, no usado
      en las reglas v1.
    """

    consciente: bool
    respira_normal: bool
    sangrado: NivelSangrado
    dolor_toracico: NivelDolorToracico
    dificultad_respiratoria: bool
    grupo_etario: GrupoEtario
