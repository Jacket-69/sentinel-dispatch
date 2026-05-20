package cl.ucen.sentinel.application;

import java.util.List;
import java.util.Objects;

/**
 * Resultado de {@link Saturacion#detectar} (RN-08, CP-10).
 *
 * <p>Inmutable. Espejo del Python {@code @dataclass(frozen=True, slots=True) EstadoSaturacion} en
 * {@code application/tipos.py}.
 *
 * <p>Atributos:
 *
 * <ul>
 *   <li>{@code saturada}: {@code true} si no existe ninguna unidad en estado DISPONIBLE en la flota
 *       evaluada. Coincide con "ninguna unidad disponible" del SRS sec. 2.7 RN-08.
 *   <li>{@code candidatasRedireccion}: lista inmutable con las unidades EnRuta ordenadas por {@code
 *       progresoPct} ascendente. Vacía cuando {@code saturada} es {@code false} (no se calculan
 *       candidatas si hay flota libre).
 * </ul>
 *
 * @param saturada {@code true} si no hay ninguna unidad Disponible en la flota
 * @param candidatasRedireccion lista inmutable de candidatas a re-dirección manual; vacía si no hay
 *     saturación
 */
public record EstadoSaturacion(boolean saturada, List<CandidataRedireccion> candidatasRedireccion) {

  /**
   * Compact constructor: envuelve la lista de candidatas con {@code List.copyOf} para garantizar
   * inmutabilidad.
   */
  public EstadoSaturacion {
    Objects.requireNonNull(candidatasRedireccion, "candidatasRedireccion no puede ser nula");
    candidatasRedireccion = List.copyOf(candidatasRedireccion);
  }
}
