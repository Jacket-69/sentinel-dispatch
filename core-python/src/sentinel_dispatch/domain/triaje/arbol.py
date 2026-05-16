"""Árbol MPDS-subset — clasificación del incidente.

Función pura :func:`clasificar_mpds` que mapea una :class:`RespuestaTriaje` a
una :class:`CategoriaMPDS` siguiendo el árbol del SRS sec. 2.6-A.

Esta implementación es **fiel al texto literal del SRS**. Existen
inconsistencias conocidas entre el árbol del SRS y el dataset sec. 2.12 que
requieren refinamiento posterior (ver `NOTAS DE INCONSISTENCIA` al final).
"""

from __future__ import annotations

from sentinel_dispatch.domain.triaje.tipos import CategoriaMPDS, GrupoEtario, RespuestaTriaje


def clasificar_mpds(respuesta: RespuestaTriaje) -> CategoriaMPDS:
    """Clasifica el incidente según el árbol MPDS-subset.

    Reglas (en orden de evaluación), tal como el SRS sec. 2.6-A las enuncia:

    1. ``consciente = No`` ∧ ``respira = No``     → Echo
    2. ``consciente = No`` ∧ ``respira = Sí``    → Delta
    3. ``consciente = Sí`` ∧ ``dolor_toracico = Sí``                       → Delta
    4. ``consciente = Sí`` ∧ ``sangrado_activo = Sí`` ∧ ``dolor_toracico = No`` → Charlie
    5. ``consciente = Sí`` ∧ ``sangrado_activo = No`` ∧ ``dificultad_respiratoria = Sí`` → Charlie
    6. ``consciente = Sí`` ∧ ``grupo_etario = Pediátrico`` ∧ síntoma moderado → Bravo
    7. resto                                                              → Alpha

    "Síntoma moderado" en regla 6 se interpreta como ``sangrado_activo`` o
    ``dificultad_respiratoria`` activos en ausencia de ``dolor_toracico`` (los
    casos críticos ya filtraron antes). Esta interpretación es consistente con
    el dataset I-02 y I-03 que califican como Bravo con sangrado leve, aunque
    el dataset no marca Pediátrico — ver NOTAS DE INCONSISTENCIA.

    Parameters
    ----------
    respuesta
        Respuestas del operador al árbol.

    Returns
    -------
    CategoriaMPDS
        Categoría asignada.
    """
    # Regla 1 y 2 — inconsciente.
    if not respuesta.consciente:
        if not respuesta.respira:
            return CategoriaMPDS.ECHO
        return CategoriaMPDS.DELTA

    # A partir de acá: consciente = Sí.
    # Regla 3 — dolor torácico domina.
    if respuesta.dolor_toracico:
        return CategoriaMPDS.DELTA

    # Regla 4 — sangrado activo sin dolor torácico.
    if respuesta.sangrado_activo:
        return CategoriaMPDS.CHARLIE

    # Regla 5 — dificultad respiratoria sin sangrado.
    if respuesta.dificultad_respiratoria:
        return CategoriaMPDS.CHARLIE

    # Regla 6 — pediátrico con síntoma moderado.
    # (En este punto: consciente, sin dolor torácico, sin sangrado, sin dificultad respiratoria.)
    # No quedan síntomas "moderados" activos; la rama Bravo del SRS literal no se
    # gatilla con esta interpretación estricta. Se mantiene para fidelidad textual
    # — el dataset hace cumplir Bravo por otras vías (ver NOTAS DE INCONSISTENCIA).
    if respuesta.grupo_etario == GrupoEtario.PEDIATRICO:  # noqa: SIM103 (claridad)
        return CategoriaMPDS.ALPHA  # fallback al no haber síntoma moderado evaluable

    # Regla 7 — resto.
    return CategoriaMPDS.ALPHA


# ---------------------------------------------------------------------------
# NOTAS DE INCONSISTENCIA (RESOLVER CON BENJAMIN ANTES DE H1)
# ---------------------------------------------------------------------------
# 1. El árbol del SRS sec. 2.6-A no distingue "dolor torácico severo" vs
#    "dolor torácico severo incapacitante", pero el dataset trata I-06 (severo)
#    como Charlie y I-08 (severo incapacitante) como Delta. Necesitamos:
#       (a) refinar el árbol para distinguir intensidades, o
#       (b) reclasificar el dataset.
#    Decisión pendiente: discutir con Fernando + revisar el SRS LaTeX vigente.
#
# 2. La regla 6 (Bravo pediátrico) habla de "síntoma moderado" sin definirlo.
#    El dataset I-02/I-03 marca Bravo con "sangrado leve, adulto/anciano" — no
#    pediátrico. Esto sugiere que la regla 6 debería ampliarse a:
#       Bravo si sangrado_activo "leve" (no calificado por dolor torácico) o
#       si síntoma menor en cualquier grupo etario.
#    Necesitamos un campo nuevo `intensidad_sangrado` o similar.
#
# 3. La sec. 2.5 del SRS define las entradas como booleanos puros. La
#    distinción "severo vs severo incapacitante" exige al menos una variable
#    categórica adicional. Esta es la deuda de modelado más urgente para H1.
#
# Estas inconsistencias se documentarán formalmente en un ADR cuando se
# resuelvan, junto con la corrección al SRS si aplica.
