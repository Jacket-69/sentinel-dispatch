package cl.ucen.sentinel.domain.triaje;

/**
 * Nivel de sangrado visible.
 *
 * <p>Espejo exacto del Python {@code NivelSangrado}. Mapeo a MPDS Protocol 21
 * (Hemorrhage/Lacerations):
 *
 * <ul>
 *   <li>{@link #NINGUNO}: sin sangrado visible. No aplica Protocol 21.
 *   <li>{@link #MODERADO}: sangrado uncontrolled fuera de zona peligrosa (≈ Protocol 21-B-2).
 *   <li>{@link #ACTIVO}: sangrado uncontrolled sin verificación de ubicación. Adaptación SAMU Chile
 *       (eleva a Charlie). Detalle en ADR-0009.
 *   <li>{@link #PELIGROSO}: sangrado arterial o en zonas críticas (axila, ingle, cuello) — ≈
 *       Protocol 21-D-4.
 * </ul>
 */
public enum NivelSangrado {
  NINGUNO("Ninguno"),
  MODERADO("Moderado"),
  ACTIVO("Activo"),
  PELIGROSO("Peligroso");

  private final String valor;

  NivelSangrado(String valor) {
    this.valor = valor;
  }

  public String valor() {
    return valor;
  }

  /**
   * Construye el nivel de sangrado a partir del valor de texto.
   *
   * @param valor valor de texto (ej. "Ninguno", "Peligroso")
   * @return el nivel correspondiente
   * @throws IllegalArgumentException si el valor no existe en el dominio
   */
  public static NivelSangrado fromValor(String valor) {
    for (NivelSangrado n : values()) {
      if (n.valor.equals(valor)) {
        return n;
      }
    }
    throw new IllegalArgumentException("Nivel de sangrado desconocido: " + valor);
  }
}
