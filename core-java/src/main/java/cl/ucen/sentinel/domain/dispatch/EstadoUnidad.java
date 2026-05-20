package cl.ucen.sentinel.domain.dispatch;

/**
 * Estado operativo del móvil SAMU.
 *
 * <p>Espejo del Python {@code EstadoUnidad(StrEnum)}. La unidad en {@link #TALLER} está excluida
 * del cálculo de costo bajo cualquier circunstancia (RN-04).
 *
 * <p>Transiciones válidas (FSM; no se hace cumplir aquí — vive en application/):
 *
 * <ul>
 *   <li>{@code DISPONIBLE} → {@code EN_RUTA} (despacho confirmado).
 *   <li>{@code EN_RUTA} → {@code EN_ESCENA} (llegada al incidente) ó {@code EN_RUTA} (re-despacho
 *       RN-06) ó {@code DISPONIBLE} (cancelación).
 *   <li>{@code EN_ESCENA} → {@code EN_RUTA} (traslado a hospital) ó {@code DISPONIBLE}
 *       (finalización in-situ).
 *   <li>{@code TALLER} → {@code DISPONIBLE} (alta de mantención).
 * </ul>
 *
 * <p>Referencia: SRS sec. 2.5, RN-04.
 */
public enum EstadoUnidad {
  /** Unidad lista para despacho. */
  DISPONIBLE("Disponible"),
  /** Unidad en camino a un incidente. */
  EN_RUTA("EnRuta"),
  /** Unidad en escena atendiendo un incidente. */
  EN_ESCENA("EnEscena"),
  /** Unidad fuera de servicio por mantención. Excluida del cálculo por RN-04. */
  TALLER("Taller");

  /** Valor serializable equivalente al {@code StrEnum.value} del Python. */
  private final String valor;

  EstadoUnidad(String valor) {
    this.valor = valor;
  }

  /** Devuelve el valor de texto equivalente al {@code StrEnum.value} de Python. */
  public String valor() {
    return valor;
  }

  /**
   * Construye el estado a partir del valor de texto (equivalente a {@code EstadoUnidad(str)} en
   * Python). Lanza {@link IllegalArgumentException} si el valor no existe.
   *
   * @param valor valor de texto (ej. "Disponible", "EnRuta")
   * @return el estado correspondiente
   * @throws IllegalArgumentException si el valor no corresponde a ningún estado
   */
  public static EstadoUnidad fromValor(String valor) {
    for (EstadoUnidad e : values()) {
      if (e.valor.equals(valor)) {
        return e;
      }
    }
    throw new IllegalArgumentException("Estado de unidad desconocido: " + valor);
  }
}
