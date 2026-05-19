package cl.ucen.sentinel.domain.triaje;

/**
 * Árbol MPDS-subset — clasificación del incidente.
 *
 * <p>Espejo bit-exacto del Python {@code clasificar_mpds(respuesta)} del módulo {@code arbol}.
 * Implementa las mismas 9 reglas en el mismo orden estricto de evaluación.
 *
 * <p>Las 9 reglas siguen el árbol del SRS sec. 2.6-A:
 *
 * <ol>
 *   <li>{@code consciente=No ∧ respiraNormal=No} → <b>Echo</b> (9-E-1 / 31-E-1)
 *   <li>{@code consciente=No ∧ respiraNormal=Sí} → <b>Delta</b> (31-D-2)
 *   <li>{@code consciente=Sí ∧ sangrado=PELIGROSO} → <b>Delta</b> (21-D-4)
 *   <li>{@code consciente=Sí ∧ dolorToracico=CRITICO} → <b>Delta</b> (10-D)
 *   <li>{@code consciente=Sí ∧ dolorToracico=PRESENTE} → <b>Charlie</b> (10-C)
 *   <li>{@code consciente=Sí ∧ dificultadRespiratoria=Sí} → <b>Charlie</b> (31-C-1 / 6-C)
 *   <li>{@code consciente=Sí ∧ sangrado=ACTIVO} → <b>Charlie</b> (adaptación SAMU)
 *   <li>{@code consciente=Sí ∧ sangrado=MODERADO} → <b>Bravo</b> (21-B-2)
 *   <li>{@code consciente=Sí ∧ (resto)} → <b>Alpha</b> (sin Chief Complaint)
 * </ol>
 *
 * <p>La regla 7 incorpora una adaptación al contexto SAMU Chile: sangrado uncontrolled sin
 * verificación de ubicación geográfica se eleva sistemáticamente a Charlie como precaución, en
 * lugar de Bravo (que sería la lectura MPDS literal 21-B-2). Justificación completa en ADR-0009.
 *
 * <p>Clase de utilidad pura — no instanciar.
 */
public final class Arbol {

  private Arbol() {
    throw new AssertionError("Clase de utilidad — no instanciar");
  }

  /**
   * Clasifica el incidente según el árbol MPDS-subset.
   *
   * <p>Las 9 reglas se evalúan en orden estricto; la primera que satisface sus condiciones
   * determina la categoría. Comportamiento bit-exacto al Python {@code clasificar_mpds}.
   *
   * @param respuesta respuestas del operador al árbol; no puede ser {@code null}
   * @return categoría MPDS asignada
   * @throws NullPointerException si {@code respuesta} es {@code null}
   */
  public static CategoriaMPDS clasificarMpds(RespuestaTriaje respuesta) {
    java.util.Objects.requireNonNull(respuesta, "respuesta no puede ser nula");

    // Reglas 1 y 2 — paciente inconsciente. respiraNormal distingue arrest vs effective breathing.
    if (!respuesta.consciente()) {
      if (!respuesta.respiraNormal()) {
        return CategoriaMPDS.ECHO; // Regla 1 → 9-E-1 / 31-E-1
      }
      return CategoriaMPDS.DELTA; // Regla 2 → 31-D-2
    }

    // A partir de acá: paciente consciente.
    // Regla 3 — sangrado peligroso domina (zona crítica o arterial).
    if (respuesta.sangrado() == NivelSangrado.PELIGROSO) {
      return CategoriaMPDS.DELTA; // → 21-D-4
    }

    // Regla 4 — dolor torácico crítico (con síntoma asociado severo).
    if (respuesta.dolorToracico() == NivelDolorToracico.CRITICO) {
      return CategoriaMPDS.DELTA; // → 10-D
    }

    // Regla 5 — dolor torácico presente (aislado).
    if (respuesta.dolorToracico() == NivelDolorToracico.PRESENTE) {
      return CategoriaMPDS.CHARLIE; // → 10-C
    }

    // Regla 6 — dificultad respiratoria (alerta + abnormal breathing).
    if (respuesta.dificultadRespiratoria()) {
      return CategoriaMPDS.CHARLIE; // → 31-C-1 / 6-C
    }

    // Regla 7 — sangrado activo sin verificar ubicación (adaptación SAMU).
    if (respuesta.sangrado() == NivelSangrado.ACTIVO) {
      return CategoriaMPDS.CHARLIE; // adaptación SAMU Chile; ver ADR-0009
    }

    // Regla 8 — sangrado moderado (serious hemorrhage no peligroso).
    if (respuesta.sangrado() == NivelSangrado.MODERADO) {
      return CategoriaMPDS.BRAVO; // → 21-B-2
    }

    // Regla 9 — resto.
    return CategoriaMPDS.ALPHA;
  }
}
