package cl.ucen.sentinel.domain.dispatch;

import cl.ucen.sentinel.domain.triaje.CategoriaMPDS;
import java.util.Objects;

/**
 * Evento médico ya triado, listo para entrar al despacho.
 *
 * <p>Inmutable. Espejo del Python {@code @dataclass(frozen=True, slots=True) Incidente}. Combina la
 * coordenada validada (RN-01) con el resultado del árbol de triaje (categoría MPDS) y el
 * identificador del evento.
 *
 * <p>Atributos según SRS sec. 2.5:
 *
 * <ul>
 *   <li>{@code id}: identificador único ("I-01".."I-12" en el dataset H1).
 *   <li>{@code lat}, {@code lon}: coordenadas EPSG:4326 del incidente; ya validadas por el adapter
 *       de entrada antes de construir este objeto.
 *   <li>{@code categoriaMpds}: salida del árbol MPDS (Alpha..Echo). Entra en la función de costo
 *       vía la tabla de penalización de idoneidad.
 *   <li>{@code timestampIso}: marca temporal ISO 8601 con offset ("...-04:00"). Opaca para el
 *       dominio dispatch.
 * </ul>
 *
 * @param id identificador único del incidente
 * @param lat latitud EPSG:4326
 * @param lon longitud EPSG:4326
 * @param categoriaMpds categoría MPDS asignada por el árbol de triaje
 * @param timestampIso marca temporal ISO 8601 con offset
 */
public record Incidente(
    String id, double lat, double lon, CategoriaMPDS categoriaMpds, String timestampIso) {

  /** Compact constructor: valida que los campos de referencia no sean nulos. */
  public Incidente {
    Objects.requireNonNull(id, "id no puede ser nulo");
    Objects.requireNonNull(categoriaMpds, "categoriaMpds no puede ser nula");
    Objects.requireNonNull(timestampIso, "timestampIso no puede ser nulo");
  }
}
