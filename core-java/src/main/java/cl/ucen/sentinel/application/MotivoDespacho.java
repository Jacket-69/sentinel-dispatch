package cl.ucen.sentinel.application;

/**
 * Razón por la que {@link DespacharAmbulancia#despachar} retornó su resultado.
 *
 * <p>Espejo del Python {@code MotivoDespacho(StrEnum)} en {@code application/tipos.py}. Útil para
 * el log JSONL (RF-06, ADR-0007), la auditoría académica y para que el operador entienda el camino
 * tomado por el algoritmo.
 *
 * <ul>
 *   <li>{@link #OPTIMO}: unidad seleccionada por argmin con costo finito y penalización 0
 *       (combinación ideal MPDS × Tipo).
 *   <li>{@link #PENALIZADO}: la elegida tiene penalización {@literal >} 0 finita (Charlie +
 *       Básica). La idoneidad no es ideal pero el costo total sigue siendo el mínimo de la flota.
 *   <li>{@link #SUBOPTIMO_RN02}: fallback RN-02 — la idoneidad ideal es ∞ (Echo/Delta + Básica)
 *       pero la única Disponible es Básica; se despacha con flag {@code despachoSuboptimo} para no
 *       bloquear el servicio. Documentado en ADR-0015.
 *   <li>{@link #SATURACION}: no hay unidad Disponible elegible. No se genera despacho; el
 *       orquestador retorna candidatas EnRuta para que el operador evalúe redirigir manualmente
 *       (RN-08, CP-10).
 * </ul>
 *
 * <p>Fuente normativa: SRS sec. 2.6-D / 2.6-E, 2.7 RN-02, RN-08. Decisión arquitectónica: ADR-0015.
 */
public enum MotivoDespacho {

  /** Selección óptima: penalización cero, costo finito. */
  OPTIMO("optimo"),

  /** Selección penalizada: penalización finita {@literal >} 0 (p.ej. Charlie + Básica). */
  PENALIZADO("penalizado"),

  /** Fallback RN-02: única Básica disponible para incidente Echo/Delta. */
  SUBOPTIMO_RN02("suboptimo_rn02"),

  /** Sin unidades disponibles; se informan candidatas EnRuta para re-dirección manual (RN-08). */
  SATURACION("saturacion");

  /** Valor serializable equivalente al {@code StrEnum.value} del Python. */
  private final String valor;

  MotivoDespacho(String valor) {
    this.valor = valor;
  }

  /**
   * Devuelve el valor de texto equivalente al {@code StrEnum.value} de Python.
   *
   * @return cadena de texto ("optimo", "penalizado", "suboptimo_rn02" o "saturacion")
   */
  public String valor() {
    return valor;
  }

  /**
   * Construye el motivo a partir del valor de texto (equivalente a {@code MotivoDespacho(str)} en
   * Python). Lanza {@link IllegalArgumentException} si el valor no existe.
   *
   * @param valor valor de texto (p.ej. "optimo", "saturacion")
   * @return el motivo correspondiente
   * @throws IllegalArgumentException si el valor no corresponde a ningún motivo conocido
   */
  public static MotivoDespacho fromValor(String valor) {
    for (MotivoDespacho m : values()) {
      if (m.valor.equals(valor)) {
        return m;
      }
    }
    throw new IllegalArgumentException("MotivoDespacho desconocido: " + valor);
  }
}
