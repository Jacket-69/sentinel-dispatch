package cl.ucen.sentinel.application;

import cl.ucen.sentinel.domain.dispatch.CandidatoDespacho;
import cl.ucen.sentinel.domain.dispatch.CostoDespacho;
import cl.ucen.sentinel.domain.dispatch.Incidente;
import cl.ucen.sentinel.domain.dispatch.Unidad;
import java.util.List;
import java.util.Objects;

/**
 * Salida del orquestador {@link DespacharAmbulancia#despachar} — todo lo necesario para persistir
 * el log (RF-06) y mostrarle al operador qué hizo el sistema.
 *
 * <p>Inmutable. Espejo del Python {@code @dataclass(frozen=True, slots=True) ResultadoDespacho} en
 * {@code application/tipos.py}.
 *
 * <p>Cuando {@code motivo == SATURACION}, {@code elegida} es {@code null}, {@code costoElegida} es
 * {@code null} y {@code saturacion} trae las candidatas de re-dirección. En el resto de los casos,
 * {@code elegida} y {@code costoElegida} están poblados y {@code saturacion} puede ser {@code
 * null}.
 *
 * <p>Atributos:
 *
 * <ul>
 *   <li>{@code incidente}: el incidente despachado (o intentado despachar).
 *   <li>{@code elegida}: unidad seleccionada por el argmin, o {@code null} si el sistema reportó
 *       saturación.
 *   <li>{@code costoElegida}: {@link CostoDespacho} de la ganadora, o {@code null}.
 *   <li>{@code motivo}: {@link MotivoDespacho} explicando por qué este resultado y no otro.
 *   <li>{@code despachoSuboptimo}: {@code true} solo cuando {@code motivo} es {@link
 *       MotivoDespacho#SUBOPTIMO_RN02}. Campo dedicado para que el log JSONL (RF-06) lo persista
 *       bit-exacto sin re-derivarlo del {@code motivo} en cada lectura.
 *   <li>{@code candidatos}: lista inmutable con todos los {@link CandidatoDespacho} evaluados por
 *       el argmin, ordenados por {@code (costo, id)}. Útil para auditoría académica (CP-04 /
 *       CP-11).
 *   <li>{@code saturacion}: {@link EstadoSaturacion} cuando {@code motivo} es {@link
 *       MotivoDespacho#SATURACION}, o {@code null}. Contiene las candidatas EnRuta que el operador
 *       puede redirigir manualmente (CP-10).
 *   <li>{@code rutaNodos}: lista inmutable de IDs de nodo OSM que el A* encontró para la unidad
 *       elegida. Vacía cuando {@code motivo == SATURACION} o cuando la unidad elegida no tiene ruta
 *       disponible.
 * </ul>
 *
 * @param incidente el incidente despachado o intentado despachar
 * @param elegida unidad seleccionada, o {@code null} en saturación
 * @param costoElegida costo de la elegida, o {@code null} en saturación
 * @param motivo razón del resultado ({@link MotivoDespacho})
 * @param despachoSuboptimo {@code true} solo si motivo es {@link MotivoDespacho#SUBOPTIMO_RN02}
 * @param candidatos lista inmutable de todos los candidatos evaluados y ordenados
 * @param saturacion estado de saturación, o {@code null} si no aplica
 * @param rutaNodos lista inmutable de nodos de la ruta de la unidad elegida; vacía si no hay
 *     elegida
 */
public record ResultadoDespacho(
    Incidente incidente,
    Unidad elegida,
    CostoDespacho costoElegida,
    MotivoDespacho motivo,
    boolean despachoSuboptimo,
    List<CandidatoDespacho> candidatos,
    EstadoSaturacion saturacion,
    List<Long> rutaNodos) {

  /**
   * Compact constructor: envuelve las listas inmutables con {@code List.copyOf}. Los campos
   * nullable ({@code elegida}, {@code costoElegida}, {@code saturacion}) no se copian porque son
   * value objects o {@code null}.
   */
  public ResultadoDespacho {
    Objects.requireNonNull(incidente, "incidente no puede ser nulo");
    Objects.requireNonNull(motivo, "motivo no puede ser nulo");
    Objects.requireNonNull(candidatos, "candidatos no puede ser nulo");
    Objects.requireNonNull(rutaNodos, "rutaNodos no puede ser nulo");
    candidatos = List.copyOf(candidatos);
    rutaNodos = List.copyOf(rutaNodos);
  }
}
