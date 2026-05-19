package cl.ucen.sentinel.domain.routing;

/**
 * Heurística Haversine admisible para el A* sobre el grafo vial (ADR-0010 §1).
 *
 * <p>Espejo de {@code sentinel_dispatch/domain/routing/heuristica.py}. Calcula la distancia
 * ortodrómica entre dos nodos del grafo y la divide por la velocidad máxima del sistema,
 * produciendo un tiempo mínimo posible en segundos. La heurística es admisible: ninguna arista del
 * grafo puede recorrerse a más de {@link #V_MAX_KMH}, por lo que {@code h(n) ≤ costo_real(n,
 * destino)} para todo {@code n}.
 *
 * <p>Lógica pura: depende solo de {@code java.lang.Math} y del puerto {@link GrafoVial}.
 */
public final class Heuristica {

  /** Velocidad máxima absoluta del sistema en km/h. Espejo de {@code V_MAX_KMH = 180.0} Python. */
  public static final double V_MAX_KMH = 180.0;

  /** Velocidad máxima en m/s (≈ 38.89 m/s). Espejo de {@code V_MAX_MS} Python. */
  public static final double V_MAX_MS = V_MAX_KMH * 1000.0 / 3600.0;

  /** Radio medio de la Tierra en metros. Espejo de {@code RADIO_TIERRA_M = 6_371_000.0} Python. */
  public static final double RADIO_TIERRA_M = 6_371_000.0;

  private Heuristica() {}

  /**
   * Distancia ortodrómica entre dos puntos, en metros.
   *
   * <p>Espejo de {@code haversine_m(lat1, lon1, lat2, lon2)} Python. Fórmula Haversine clásica
   * sobre esfera de radio {@link #RADIO_TIERRA_M}.
   *
   * @param lat1 latitud del punto 1 en grados decimales
   * @param lon1 longitud del punto 1 en grados decimales
   * @param lat2 latitud del punto 2 en grados decimales
   * @param lon2 longitud del punto 2 en grados decimales
   * @return distancia en metros
   */
  public static double haversineM(double lat1, double lon1, double lat2, double lon2) {
    double lat1Rad = Math.toRadians(lat1);
    double lat2Rad = Math.toRadians(lat2);
    double dlat = lat2Rad - lat1Rad;
    double dlon = Math.toRadians(lon2 - lon1);
    double a =
        Math.sin(dlat / 2.0) * Math.sin(dlat / 2.0)
            + Math.cos(lat1Rad) * Math.cos(lat2Rad) * Math.sin(dlon / 2.0) * Math.sin(dlon / 2.0);
    double c = 2.0 * Math.asin(Math.sqrt(a));
    return RADIO_TIERRA_M * c;
  }

  /**
   * Heurística admisible h(n) para el A*: tiempo mínimo posible en segundos.
   *
   * <p>Espejo de {@code haversine_segundos(lat1, lon1, lat2, lon2)} Python. Calcula {@code
   * haversineM / V_MAX_MS}.
   *
   * @param lat1 latitud del punto 1 en grados decimales
   * @param lon1 longitud del punto 1 en grados decimales
   * @param lat2 latitud del punto 2 en grados decimales
   * @param lon2 longitud del punto 2 en grados decimales
   * @return tiempo mínimo posible en segundos
   */
  public static double haversineSegundos(double lat1, double lon1, double lat2, double lon2) {
    return haversineM(lat1, lon1, lat2, lon2) / V_MAX_MS;
  }
}
