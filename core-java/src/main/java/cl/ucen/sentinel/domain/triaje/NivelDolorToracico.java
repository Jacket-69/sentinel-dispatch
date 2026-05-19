package cl.ucen.sentinel.domain.triaje;

/**
 * Nivel de dolor torácico.
 *
 * <p>Espejo exacto del Python {@code NivelDolorToracico}. Mapeo a MPDS Protocol 10 (Chest Pain):
 *
 * <ul>
 *   <li>{@link #NINGUNO}: sin dolor torácico. No aplica Protocol 10.
 *   <li>{@link #PRESENTE}: chest pain aislado, paciente alerta, sin síntomas asociados graves (≈
 *       Protocol 10-C).
 *   <li>{@link #CRITICO}: chest pain con síntoma asociado severo (not alert, abnormal breathing,
 *       clammy, irradiación severa) — ≈ Protocol 10-D.
 * </ul>
 */
public enum NivelDolorToracico {
  NINGUNO("Ninguno"),
  PRESENTE("Presente"),
  CRITICO("Crítico");

  private final String valor;

  NivelDolorToracico(String valor) {
    this.valor = valor;
  }

  public String valor() {
    return valor;
  }

  /**
   * Construye el nivel de dolor torácico a partir del valor de texto.
   *
   * @param valor valor de texto (ej. "Ninguno", "Crítico")
   * @return el nivel correspondiente
   * @throws IllegalArgumentException si el valor no existe en el dominio
   */
  public static NivelDolorToracico fromValor(String valor) {
    for (NivelDolorToracico n : values()) {
      if (n.valor.equals(valor)) {
        return n;
      }
    }
    throw new IllegalArgumentException("Nivel de dolor torácico desconocido: " + valor);
  }
}
