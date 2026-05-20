package cl.ucen.sentinel.domain.dispatch;

/**
 * Tipo de móvil SAMU según capacidad de soporte vital.
 *
 * <p>Espejo del Python {@code TipoUnidad(StrEnum)}. El mapeo a la realidad SAMU Chile se documenta
 * en ADR-0009.
 *
 * <ul>
 *   <li><b>AVANZADA</b> (ALS — Advanced Life Support): paramédico + médico tripulante. Apta para
 *       todas las categorías MPDS (Alpha..Echo).
 *   <li><b>BASICA</b> (BLS — Basic Life Support): tripulación TENS sin capacidades ALS. Apta para
 *       Alpha/Bravo sin penalización; penalizada para Charlie; excluida (penalización ∞) para
 *       Delta/Echo.
 * </ul>
 *
 * <p>Referencia: SRS sec. 2.5, ADR-0009.
 */
public enum TipoUnidad {
  /** ALS — soporte vital avanzado; paramédico + médico a bordo. */
  AVANZADA("Avanzada"),
  /** BLS — soporte vital básico; tripulación TENS. */
  BASICA("Básica");

  /** Valor serializable equivalente al {@code StrEnum.value} del Python. */
  private final String valor;

  TipoUnidad(String valor) {
    this.valor = valor;
  }

  /** Devuelve el valor de texto equivalente al {@code StrEnum.value} de Python. */
  public String valor() {
    return valor;
  }

  /**
   * Construye el tipo a partir del valor de texto (equivalente a {@code TipoUnidad(str)} en
   * Python). Lanza {@link IllegalArgumentException} si el valor no existe.
   *
   * @param valor valor de texto (ej. "Avanzada", "Básica")
   * @return el tipo correspondiente
   * @throws IllegalArgumentException si el valor no corresponde a ningún tipo
   */
  public static TipoUnidad fromValor(String valor) {
    for (TipoUnidad t : values()) {
      if (t.valor.equals(valor)) {
        return t;
      }
    }
    throw new IllegalArgumentException("Tipo de unidad desconocido: " + valor);
  }
}
