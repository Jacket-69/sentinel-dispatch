package cl.ucen.sentinel.domain.dispatch;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;

/**
 * Selección óptima de unidad por {@code argmin_u Costo(u, i)} (SRS sec. 2.6-D).
 *
 * <p>Implementa RF-05: dada una flota de unidades disponibles y un incidente triado, computa el
 * costo de cada unidad y selecciona la de costo mínimo. Ante empate de costo, desempata
 * lexicográficamente por {@code unidad.id} ascendente (CP-11).
 *
 * <p>Convención de input:
 *
 * <ul>
 *   <li>El filtrado por RN-04 (Taller) se hace silenciosamente aquí — la función está diseñada para
 *       evaluar flotas completas donde una unidad en Taller no debería abortar todo el cálculo.
 *   <li>Las unidades sin entrada en {@code tiemposViaje} se excluyen silenciosamente. El caller es
 *       responsable de proveer tViaje para todas las unidades que quiere evaluar.
 *   <li>Valores NaN o negativos del mapa SÍ propagan {@link TViajeInvalidoException} — son errores
 *       upstream que no deben silenciarse.
 * </ul>
 *
 * <p>Clase de utilidad pura — no instanciar.
 *
 * <p>Fuente normativa: SRS sec. 2.6-D, CP-04, CP-05, CP-11. Decisión arquitectónica: ADR-0014.
 */
public final class Seleccion {

  private Seleccion() {
    throw new AssertionError("Clase de utilidad — no instanciar");
  }

  /** Comparador: costo ascendente, luego ID de unidad lexicográfico ascendente (CP-11). */
  private static final Comparator<CandidatoDespacho> ORDEN_CANDIDATO =
      Comparator.comparingDouble((CandidatoDespacho c) -> c.costo().valorTotalS())
          .thenComparing(c -> c.unidad().id());

  /**
   * Selecciona la unidad de menor costo para el incidente (RF-05).
   *
   * <p>Las unidades en estado {@link EstadoUnidad#TALLER} se excluyen silenciosamente (RN-04). Las
   * unidades sin entrada en {@code tiemposViaje} también se excluyen.
   *
   * <p>Cuando ninguna unidad tiene costo finito (todas son infinitas por penalización, o la flota
   * está vacía/toda en Taller), {@code ResultadoSeleccion.elegida} es {@code null}.
   *
   * @param unidades flota a evaluar (puede incluir unidades en Taller — se filtran silenciosamente)
   * @param incidente evento triado con categoría MPDS
   * @param tiemposViaje mapa {@code unidad.id → tViajeS} en segundos; {@code Double
   *     .POSITIVE_INFINITY} resulta en costo infinito; NaN o negativo propaga {@link
   *     TViajeInvalidoException}
   * @return {@link ResultadoSeleccion} con la elegida (o {@code null}), el costo de la elegida y la
   *     lista ordenada de todos los candidatos evaluados
   * @throws TViajeInvalidoException si algún tViaje en el mapa es NaN o negativo
   */
  public static ResultadoSeleccion seleccionarUnidad(
      Iterable<Unidad> unidades, Incidente incidente, Map<String, Double> tiemposViaje) {

    List<CandidatoDespacho> candidatos = new ArrayList<>();

    for (Unidad unidad : unidades) {
      // RN-04: Taller se excluye silenciosamente (no lanza, no agrega al log).
      if (unidad.estado() == EstadoUnidad.TALLER) {
        continue;
      }
      // Unidad sin tiempo de viaje provisto → excluida silenciosamente.
      Double t = tiemposViaje.get(unidad.id());
      if (t == null) {
        continue;
      }
      // NaN o negativo propaga la excepción (error upstream, no se silencia).
      CostoDespacho c = FuncionCosto.costo(unidad, incidente, t);
      candidatos.add(new CandidatoDespacho(unidad, t, c));
    }

    candidatos.sort(ORDEN_CANDIDATO);

    // Primer candidato con costo finito es el ganador del argmin.
    CandidatoDespacho primeraFinita =
        candidatos.stream().filter(c -> !c.costo().esInfinito()).findFirst().orElse(null);

    if (primeraFinita == null) {
      return new ResultadoSeleccion(null, null, candidatos);
    }

    return new ResultadoSeleccion(primeraFinita.unidad(), primeraFinita.costo(), candidatos);
  }
}
