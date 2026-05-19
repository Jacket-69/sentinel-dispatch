package cl.ucen.sentinel.domain.triaje;

/**
 * Categorías del subset MPDS aplicado por Sentinel-Dispatch.
 *
 * <p>Orden estricto de criticidad creciente: ALPHA &lt; BRAVO &lt; CHARLIE &lt; DELTA &lt; ECHO. El
 * orden natural del enum ({@link #ordinal()}) replica el orden de declaración del Python {@code
 * CategoriaMPDS}, garantizando equivalencia bit-exacta de comparaciones.
 *
 * <p>Niveles MPDS oficiales (Priority Dispatch Corp):
 *
 * <ul>
 *   <li><b>ALPHA</b>: BLS no urgente (Básica, sin sirena).
 *   <li><b>BRAVO</b>: BLS urgente (Básica, con sirena).
 *   <li><b>CHARLIE</b>: ALS no urgente (Avanzada, sin sirena).
 *   <li><b>DELTA</b>: ALS urgente (Avanzada, con sirena).
 *   <li><b>ECHO</b>: ALS + recursos múltiples (paro inminente).
 * </ul>
 *
 * <p>Referencia: SRS sec. 2.6-A, ADR-0009, ADR-0008.
 */
public enum CategoriaMPDS {
  /** BLS no urgente — sin sirena. */
  ALPHA("Alpha"),
  /** BLS urgente — con sirena. */
  BRAVO("Bravo"),
  /** ALS no urgente — sin sirena. */
  CHARLIE("Charlie"),
  /** ALS urgente — con sirena. */
  DELTA("Delta"),
  /** ALS + recursos múltiples — paro inminente. */
  ECHO("Echo");

  /** Valor serializable equivalente al {@code StrEnum} value del Python. */
  private final String valor;

  CategoriaMPDS(String valor) {
    this.valor = valor;
  }

  /** Devuelve el valor de texto equivalente al {@code StrEnum.value} de Python. */
  public String valor() {
    return valor;
  }

  /**
   * Construye la categoría a partir del valor de texto (equivalente a {@code CategoriaMPDS(str)} en
   * Python). Lanza {@link IllegalArgumentException} si el valor no existe.
   *
   * @param valor valor de texto (ej. "Alpha", "Echo")
   * @return la categoría correspondiente
   * @throws IllegalArgumentException si el valor no corresponde a ninguna categoría
   */
  public static CategoriaMPDS fromValor(String valor) {
    for (CategoriaMPDS c : values()) {
      if (c.valor.equals(valor)) {
        return c;
      }
    }
    throw new IllegalArgumentException("Categoría MPDS desconocida: " + valor);
  }
}
