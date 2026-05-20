package cl.ucen.sentinel.domain.dispatch;

/**
 * El tiempo de viaje no es finito o es negativo.
 *
 * <p>Espejo del Python {@code TViajeInvalidoError(ValueError)}. Casos detectados:
 *
 * <ul>
 *   <li>{@code tViajeS < 0}: imposible físicamente.
 *   <li>{@code tViajeS} es {@code NaN}: probablemente un error de A* o de conversión upstream;
 *       preferimos fallar antes que propagar NaN hasta el argmin.
 * </ul>
 *
 * <p>{@code tViajeS == Double.POSITIVE_INFINITY} se acepta como valor válido (representa "no hay
 * ruta desde la base de la unidad al incidente") y resulta en {@code CostoDespacho.esInfinito =
 * true}.
 */
public class TViajeInvalidoException extends RuntimeException {

  /**
   * Construye la excepción con un mensaje descriptivo.
   *
   * @param mensaje mensaje que incluye el valor inválido, el ID de la unidad y el ID del incidente
   */
  public TViajeInvalidoException(String mensaje) {
    super(mensaje);
  }
}
