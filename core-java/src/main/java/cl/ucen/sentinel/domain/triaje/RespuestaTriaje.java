package cl.ucen.sentinel.domain.triaje;

import java.util.Objects;

/**
 * Respuestas del operador al árbol MPDS-subset.
 *
 * <p>Inmutable. Espejo exacto del Python {@code @dataclass(frozen=True, slots=True)
 * RespuestaTriaje}. El record de Java 21 garantiza inmutabilidad equivalente al {@code frozen=True}
 * del Python.
 *
 * <p>Validar consistencia de campos al construir es responsabilidad del adapter de entrada
 * (interfaces/cli o interfaces/api), no del dominio. El dominio no valida — replica el
 * comportamiento Python donde el dataclass no tiene {@code __post_init__}.
 *
 * <p>Atributos según SRS sec. 2.5:
 *
 * <ul>
 *   <li>{@code consciente}: ¿el paciente está consciente?
 *   <li>{@code respiraNormal}: ¿respira con normalidad? Solo se evalúa cuando {@code
 *       consciente=false}; el record acepta el valor siempre por uniformidad estructural.
 *   <li>{@code sangrado}: nivel de sangrado visible.
 *   <li>{@code dolorToracico}: nivel de dolor torácico.
 *   <li>{@code dificultadRespiratoria}: presencia de dificultad respiratoria.
 *   <li>{@code grupoEtario}: pediátrico, adulto o anciano. Reservado, no usado en las reglas v1.
 * </ul>
 *
 * @param consciente si el paciente está consciente
 * @param respiraNormal si el paciente respira con normalidad
 * @param sangrado nivel de sangrado visible
 * @param dolorToracico nivel de dolor torácico
 * @param dificultadRespiratoria si hay dificultad respiratoria
 * @param grupoEtario grupo etario del paciente
 */
public record RespuestaTriaje(
    boolean consciente,
    boolean respiraNormal,
    NivelSangrado sangrado,
    NivelDolorToracico dolorToracico,
    boolean dificultadRespiratoria,
    GrupoEtario grupoEtario) {

  /** Compact constructor: valida que los campos de referencia no sean nulos. */
  public RespuestaTriaje {
    Objects.requireNonNull(sangrado, "sangrado no puede ser nulo");
    Objects.requireNonNull(dolorToracico, "dolorToracico no puede ser nulo");
    Objects.requireNonNull(grupoEtario, "grupoEtario no puede ser nulo");
  }
}
