package cl.ucen.sentinel.application;

import cl.ucen.sentinel.domain.dispatch.Unidad;
import java.util.Objects;

/**
 * Unidad EnRuta candidata a re-dirección en caso de saturación (RN-08).
 *
 * <p>Inmutable. Espejo del Python {@code @dataclass(frozen=True, slots=True) CandidataRedireccion}
 * en {@code application/tipos.py}. Las candidatas se ordenan por {@code progresoPct} ascendente
 * para que el operador vea primero las que recién partieron — son las menos costosas operativa y
 * emocionalmente de redirigir (RN-06 §"el paciente ya escucha la sirena llegando").
 *
 * @param unidad móvil SAMU actualmente en estado EnRuta
 * @param progresoPct fracción del trayecto recorrido en {@code [0.0, 1.0]}; calculado por el caller
 *     con el reloj del sistema
 */
public record CandidataRedireccion(Unidad unidad, double progresoPct) {

  /** Compact constructor: valida que la unidad no sea nula. */
  public CandidataRedireccion {
    Objects.requireNonNull(unidad, "unidad no puede ser nula");
  }
}
