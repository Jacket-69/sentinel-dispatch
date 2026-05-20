package cl.ucen.sentinel.domain.dispatch;

import java.util.List;
import java.util.Objects;

/**
 * Salida de {@link Seleccion#seleccionarUnidad}.
 *
 * <p>Inmutable. Espejo del Python {@code @dataclass(frozen=True, slots=True) ResultadoSeleccion}.
 * {@code elegida} es {@code null} cuando ninguna unidad tiene costo finito (saturación de
 * idoneidad, no de capacidad — saturación de capacidad la detecta {@code application/saturacion}
 * con RN-08).
 *
 * <p>Atributos:
 *
 * <ul>
 *   <li>{@code elegida}: unidad ganadora del argmin, o {@code null}.
 *   <li>{@code costoElegida}: {@link CostoDespacho} de la ganadora, o {@code null}.
 *   <li>{@code candidatos}: lista con todos los {@link CandidatoDespacho} evaluados, ordenados por
 *       {@code (valorTotalS, unidad.id)} ascendente. Incluye los descartados con costo {@code ∞} al
 *       final. Inmutable (envuelta con {@code List.copyOf}).
 * </ul>
 *
 * @param elegida unidad elegida o {@code null} si ninguna tiene costo finito
 * @param costoElegida costo de la elegida o {@code null}
 * @param candidatos lista inmutable de todos los candidatos evaluados y ordenados
 */
public record ResultadoSeleccion(
    Unidad elegida, CostoDespacho costoElegida, List<CandidatoDespacho> candidatos) {

  /**
   * Compact constructor: envuelve la lista de candidatos con {@code List.copyOf} para garantizar
   * inmutabilidad. El caller puede pasar un {@code ArrayList} mutable sin riesgo.
   */
  public ResultadoSeleccion {
    Objects.requireNonNull(candidatos, "candidatos no puede ser nulo");
    // Inmutabilidad defensiva: List.copyOf rechaza nulos y retorna lista no modificable.
    candidatos = List.copyOf(candidatos);
  }
}
