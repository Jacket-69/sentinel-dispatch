package cl.ucen.sentinel.domain.dispatch;

/**
 * La unidad no puede entrar al cálculo bajo ninguna circunstancia.
 *
 * <p>Espejo del Python {@code UnidadInelegibleError(ValueError)}. Se lanza cuando la unidad está en
 * estado {@link EstadoUnidad#TALLER} (RN-04). El caller debe filtrar previamente la flota o atrapar
 * y excluir. Mantenida como excepción del dominio para que un olvido en el application layer falle
 * ruidoso en lugar de silenciar la regla.
 */
public class UnidadInelegibleException extends RuntimeException {

  /**
   * Construye la excepción con un mensaje descriptivo.
   *
   * @param mensaje mensaje que incluye el ID de la unidad y la regla violada
   */
  public UnidadInelegibleException(String mensaje) {
    super(mensaje);
  }
}
