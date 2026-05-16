"""Árbol MPDS-subset — clasificación del incidente.

Función pura :func:`clasificar_mpds` que mapea una :class:`RespuestaTriaje` a
una :class:`CategoriaMPDS` siguiendo el árbol del SRS sec. 2.6-A.

Implementa 9 reglas en orden de evaluación. Cada regla está fundamentada en
un determinante MPDS oficial (Priority Dispatch Corp). Ver tabla completa
en SRS sec. 2.6-A.1 y la decisión arquitectónica ADR-0009.

Verificación: las 9 reglas cubren los 12 incidentes del dataset de aceptación
(SRS sec. 2.12) con clasificación exacta.
"""

from __future__ import annotations

from sentinel_dispatch.domain.triaje.tipos import (
    CategoriaMPDS,
    NivelDolorToracico,
    NivelSangrado,
    RespuestaTriaje,
)


def clasificar_mpds(respuesta: RespuestaTriaje) -> CategoriaMPDS:
    """Clasifica el incidente según el árbol MPDS-subset.

    Las 9 reglas se evalúan en orden estricto; la primera que satisface sus
    condiciones determina la categoría:

    1. ``consciente=No ∧ respira_normal=No``           → **Echo**     (9-E-1 / 31-E-1)
    2. ``consciente=No ∧ respira_normal=Sí``           → **Delta**    (31-D-2)
    3. ``consciente=Sí ∧ sangrado=PELIGROSO``          → **Delta**    (21-D-4)
    4. ``consciente=Sí ∧ dolor_toracico=CRITICO``      → **Delta**    (10-D)
    5. ``consciente=Sí ∧ dolor_toracico=PRESENTE``     → **Charlie**  (10-C)
    6. ``consciente=Sí ∧ dificultad_respiratoria=Sí``  → **Charlie**  (31-C-1 / 6-C)
    7. ``consciente=Sí ∧ sangrado=ACTIVO``             → **Charlie**  (adaptación SAMU)
    8. ``consciente=Sí ∧ sangrado=MODERADO``           → **Bravo**    (21-B-2)
    9. ``consciente=Sí ∧ (resto)``                     → **Alpha**    (sin Chief Complaint)

    La regla 7 incorpora una adaptación al contexto SAMU Chile: sangrado
    uncontrolled sin verificación de ubicación geográfica se eleva
    sistemáticamente a Charlie como precaución, en lugar de Bravo (que
    sería la lectura MPDS literal 21-B-2). Justificación completa en ADR-0009.

    Parameters
    ----------
    respuesta
        Respuestas del operador al árbol.

    Returns
    -------
    CategoriaMPDS
        Categoría asignada.

    Examples
    --------
    >>> from sentinel_dispatch.domain.triaje import (
    ...     CategoriaMPDS,
    ...     GrupoEtario,
    ...     NivelDolorToracico,
    ...     NivelSangrado,
    ...     RespuestaTriaje,
    ...     clasificar_mpds,
    ... )
    >>> # I-10 del dataset: paro cardíaco
    >>> r = RespuestaTriaje(
    ...     consciente=False,
    ...     respira_normal=False,
    ...     sangrado=NivelSangrado.NINGUNO,
    ...     dolor_toracico=NivelDolorToracico.NINGUNO,
    ...     dificultad_respiratoria=False,
    ...     grupo_etario=GrupoEtario.ADULTO,
    ... )
    >>> clasificar_mpds(r) is CategoriaMPDS.ECHO
    True
    """
    # Regla 1 y 2 — paciente inconsciente. respira_normal distingue arrest vs effective breathing.
    if not respuesta.consciente:
        if not respuesta.respira_normal:
            return CategoriaMPDS.ECHO  # Regla 1 → 9-E-1 / 31-E-1
        return CategoriaMPDS.DELTA  # Regla 2 → 31-D-2

    # A partir de acá: paciente consciente.
    # Regla 3 — sangrado peligroso domina (zona crítica o arterial).
    if respuesta.sangrado is NivelSangrado.PELIGROSO:
        return CategoriaMPDS.DELTA  # → 21-D-4

    # Regla 4 — dolor torácico crítico (con síntoma asociado severo).
    if respuesta.dolor_toracico is NivelDolorToracico.CRITICO:
        return CategoriaMPDS.DELTA  # → 10-D

    # Regla 5 — dolor torácico presente (aislado).
    if respuesta.dolor_toracico is NivelDolorToracico.PRESENTE:
        return CategoriaMPDS.CHARLIE  # → 10-C

    # Regla 6 — dificultad respiratoria (alerta + abnormal breathing).
    if respuesta.dificultad_respiratoria:
        return CategoriaMPDS.CHARLIE  # → 31-C-1 / 6-C

    # Regla 7 — sangrado activo sin verificar ubicación (adaptación SAMU).
    if respuesta.sangrado is NivelSangrado.ACTIVO:
        return CategoriaMPDS.CHARLIE  # adaptación SAMU Chile; ver ADR-0009

    # Regla 8 — sangrado moderado (serious hemorrhage no peligroso).
    if respuesta.sangrado is NivelSangrado.MODERADO:
        return CategoriaMPDS.BRAVO  # → 21-B-2

    # Regla 9 — resto.
    return CategoriaMPDS.ALPHA
