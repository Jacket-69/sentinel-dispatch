package cl.ucen.sentinel.application;

import cl.ucen.sentinel.domain.dispatch.EstadoUnidad;
import cl.ucen.sentinel.domain.dispatch.Unidad;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Detección de saturación de flota (SRS sec. 2.7 RN-08, CP-10).
 *
 * <p>Implementa RF-10: dada una flota completa con sus estados y opcionalmente el progreso de las
 * unidades EnRuta, determina si el sistema está saturado (no hay Disponibles) y lista las
 * candidatas a re-dirección manual ordenadas por progreso ascendente.
 *
 * <p>La saturación de capacidad detectada acá es ortogonal a la "saturación de idoneidad" que
 * {@link cl.ucen.sentinel.domain.dispatch.Seleccion#seleccionarUnidad} reporta cuando todas las
 * Disponibles tienen costo {@code ∞} (Echo/Delta + flota solo Básica). Aquella se maneja con el
 * fallback RN-02 en {@link DespacharAmbulancia}; ésta no tiene fallback automático — el operador
 * debe decidir si redirigir una EnRuta o esperar a que se libere alguna unidad.
 *
 * <p>Clase de utilidad pura — no instanciar.
 *
 * <p>Fuente normativa: SRS sec. 2.7 RN-08, sec. 2.13 CP-10. Decisión arquitectónica: ADR-0014
 * §"Separación dominio/aplicación" + ADR-0015.
 */
public final class Saturacion {

  private Saturacion() {
    throw new AssertionError("Clase de utilidad — no instanciar");
  }

  /** Comparador: progreso ascendente, luego ID de unidad lexicográfico ascendente (CP-10). */
  private static final Comparator<CandidataRedireccion> ORDEN_CANDIDATA =
      Comparator.comparingDouble(CandidataRedireccion::progresoPct)
          .thenComparing(c -> c.unidad().id());

  /**
   * Detecta saturación de flota y lista candidatas a re-dirección.
   *
   * <p>Espejo del Python {@code detectar_saturacion(flota, progreso_por_unidad)} en {@code
   * application/saturacion.py}.
   *
   * @param flota la flota completa a evaluar (cualquier estado)
   * @param progresoPorUnidad mapeo {@code unidad.id -> progresoPct} para las unidades en estado
   *     EnRuta. Las unidades EnRuta sin entrada en este mapeo se incluyen con {@code
   *     progresoPct=0.0} (asunción conservadora: recién partieron). Pasar {@code null} equivale a
   *     un mapeo vacío.
   * @return {@link EstadoSaturacion}. {@code saturada} es {@code true} si y solo si no existe
   *     ninguna unidad en estado DISPONIBLE en la flota. Cuando hay saturación, {@code
   *     candidatasRedireccion} trae las unidades EnRuta ordenadas por {@code progresoPct}
   *     ascendente; ante empate de progreso, desempate lexicográfico por {@code unidad.id}. Cuando
   *     no hay saturación, {@code candidatasRedireccion} es la lista vacía.
   */
  public static EstadoSaturacion detectar(
      Iterable<Unidad> flota, Map<String, Double> progresoPorUnidad) {
    Map<String, Double> progreso = progresoPorUnidad != null ? progresoPorUnidad : new HashMap<>();

    boolean hayDisponible = false;
    List<Unidad> enRutas = new ArrayList<>();

    for (Unidad u : flota) {
      if (u.estado() == EstadoUnidad.DISPONIBLE) {
        hayDisponible = true;
        // No rompemos el loop: necesitamos saber si hay EnRuta también para el caso de
        // hay_disponible=true (candidatas vacías en ese caso, no se necesitan).
        // Pero podemos optimizar: si ya sabemos que hay disponible, podemos retornar ya.
        break;
      }
    }

    if (hayDisponible) {
      return new EstadoSaturacion(false, List.of());
    }

    // Sin disponibles: recolectar EnRuta
    for (Unidad u : flota) {
      if (u.estado() == EstadoUnidad.EN_RUTA) {
        enRutas.add(u);
      }
    }

    List<CandidataRedireccion> candidatas = new ArrayList<>();
    for (Unidad u : enRutas) {
      double p = progreso.getOrDefault(u.id(), 0.0);
      candidatas.add(new CandidataRedireccion(u, p));
    }
    candidatas.sort(ORDEN_CANDIDATA);

    return new EstadoSaturacion(true, candidatas);
  }
}
