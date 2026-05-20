package cl.ucen.sentinel.domain.dispatch;

/**
 * Resultado de la función de costo, con desglose para auditoría.
 *
 * <p>Inmutable. Espejo del Python {@code @dataclass(frozen=True, slots=True) CostoDespacho}. {@code
 * valorTotalS} es el número que entra al argmin de la selección; los demás campos sirven para el
 * log JSONL (RF-06, ADR-0007) y para la defensa académica (CP-04, CP-05).
 *
 * <p>Atributos según SRS sec. 2.6-C:
 *
 * <ul>
 *   <li>{@code valorTotalS}: {@code α · T_viaje + β · Penalización_Idoneidad}, en segundos. {@code
 *       Double.POSITIVE_INFINITY} cuando la combinación categoría × tipo está prohibida (Echo/Delta
 *       + Básica, RN-02).
 *   <li>{@code tViajeS}: tiempo de viaje del A* (sin factores dinámicos multiplicados), en
 *       segundos. Proviene del routing.
 *   <li>{@code penalizacion}: valor de la tabla de idoneidad (0.0, 1.0, ó {@code
 *       Double.POSITIVE_INFINITY}). Antes de multiplicar por {@code β}.
 *   <li>{@code esInfinito}: cache booleano de {@code Double.isInfinite(valorTotalS)}. Evita
 *       re-comparar floats en el argmin y deja explícito el caso "unidad excluida".
 * </ul>
 *
 * @param valorTotalS valor total del costo en segundos (puede ser infinito)
 * @param tViajeS tiempo de viaje en segundos
 * @param penalizacion penalización de idoneidad antes de multiplicar por β
 * @param esInfinito {@code true} si {@code valorTotalS} es infinito
 */
public record CostoDespacho(
    double valorTotalS, double tViajeS, double penalizacion, boolean esInfinito) {}
