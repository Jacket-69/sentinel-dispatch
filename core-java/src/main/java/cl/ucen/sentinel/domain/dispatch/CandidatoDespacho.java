package cl.ucen.sentinel.domain.dispatch;

import java.util.Objects;

/**
 * Tupla (unidad, tViaje, costo) usada para auditar la selección.
 *
 * <p>Inmutable. Espejo del Python {@code @dataclass(frozen=True, slots=True) CandidatoDespacho}.
 * Una lista de {@code CandidatoDespacho} permite al application layer registrar en el log JSONL
 * (RF-06, ADR-0007) todas las unidades evaluadas y su costo asociado, no solo la elegida.
 *
 * <p>Atributos:
 *
 * <ul>
 *   <li>{@code unidad}: la unidad evaluada.
 *   <li>{@code tViajeS}: tiempo de viaje del A* hacia el incidente. Mismo valor que entró al
 *       cálculo del costo.
 *   <li>{@code costo}: {@link CostoDespacho} con el desglose ({@code valorTotalS}, {@code
 *       penalizacion}, {@code esInfinito}).
 * </ul>
 *
 * @param unidad la unidad evaluada
 * @param tViajeS tiempo de viaje en segundos
 * @param costo desglose del costo calculado
 */
public record CandidatoDespacho(Unidad unidad, double tViajeS, CostoDespacho costo) {

  /** Compact constructor: valida que los campos de referencia no sean nulos. */
  public CandidatoDespacho {
    Objects.requireNonNull(unidad, "unidad no puede ser nula");
    Objects.requireNonNull(costo, "costo no puede ser nulo");
  }
}
