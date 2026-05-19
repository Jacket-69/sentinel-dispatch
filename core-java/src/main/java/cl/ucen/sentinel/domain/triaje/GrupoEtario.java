package cl.ucen.sentinel.domain.triaje;

/**
 * Grupos etarios reconocidos por el árbol de triaje.
 *
 * <p>Espejo exacto del Python {@code GrupoEtario}. Reservado para subdeterminantes específicos (ej.
 * Protocol 6 pediátrico). No entra al árbol v1.
 *
 * <p>Referencia: SRS sec. 2.5.
 */
public enum GrupoEtario {
  PEDIATRICO("Pediátrico"),
  ADULTO("Adulto"),
  ANCIANO("Anciano");

  private final String valor;

  GrupoEtario(String valor) {
    this.valor = valor;
  }

  public String valor() {
    return valor;
  }

  /**
   * Construye el grupo etario a partir del valor de texto.
   *
   * @param valor valor de texto (ej. "Adulto", "Pediátrico")
   * @return el grupo etario correspondiente
   * @throws IllegalArgumentException si el valor no corresponde a ningún grupo
   */
  public static GrupoEtario fromValor(String valor) {
    for (GrupoEtario g : values()) {
      if (g.valor.equals(valor)) {
        return g;
      }
    }
    throw new IllegalArgumentException("Grupo etario desconocido: " + valor);
  }
}
