package cl.ucen.sentinel.domain.dispatch;

import java.util.Objects;

/**
 * Móvil SAMU con base, tipo y estado actual.
 *
 * <p>Inmutable. Espejo del Python {@code @dataclass(frozen=True, slots=True) Unidad}. Las
 * transiciones de estado se modelan como reemplazo del value object en el application layer, no
 * como mutación in-situ.
 *
 * <p>Atributos según SRS sec. 2.5:
 *
 * <ul>
 *   <li>{@code id}: identificador único ("U01".."U10" en el dataset H1). Se compara
 *       lexicográficamente para el desempate del CP-11.
 *   <li>{@code patente}: matrícula del vehículo ("AMB-001"...). Sin uso algorítmico; presente por
 *       trazabilidad operativa.
 *   <li>{@code tipo}: {@link TipoUnidad} (Avanzada o Básica). Entra en la función de costo vía la
 *       tabla de penalización de idoneidad.
 *   <li>{@code baseNombre}: nombre legible del hospital de base.
 *   <li>{@code baseLat}, {@code baseLon}: coordenadas de la base SAMU en EPSG:4326.
 *   <li>{@code estado}: {@link EstadoUnidad}. {@code TALLER} excluye del cálculo por RN-04.
 * </ul>
 *
 * @param id identificador único de la unidad
 * @param patente matrícula del vehículo
 * @param tipo tipo de móvil (Avanzada o Básica)
 * @param baseNombre nombre del hospital de base
 * @param baseLat latitud EPSG:4326 de la base
 * @param baseLon longitud EPSG:4326 de la base
 * @param estado estado operativo actual
 */
public record Unidad(
    String id,
    String patente,
    TipoUnidad tipo,
    String baseNombre,
    double baseLat,
    double baseLon,
    EstadoUnidad estado) {

  /** Compact constructor: valida que los campos de referencia no sean nulos. */
  public Unidad {
    Objects.requireNonNull(id, "id no puede ser nulo");
    Objects.requireNonNull(patente, "patente no puede ser nula");
    Objects.requireNonNull(tipo, "tipo no puede ser nulo");
    Objects.requireNonNull(baseNombre, "baseNombre no puede ser nulo");
    Objects.requireNonNull(estado, "estado no puede ser nulo");
  }
}
