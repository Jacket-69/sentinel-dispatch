package cl.ucen.sentinel.adapters.grafo;

import cl.ucen.sentinel.domain.routing.GrafoVial;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.jgrapht.graph.DefaultWeightedEdge;
import org.jgrapht.graph.DirectedWeightedPseudograph;

/**
 * Adapter que implementa {@link GrafoVial} sobre un grafo JGraphT cargado desde GraphML de OSMnx.
 *
 * <p>Espejo del adapter Python {@code OsmnxGrafoVial} en {@code adapters/grafo_osmnx.py}. OSMnx
 * serializa todos los atributos como {@code attr.type="string"} en el GraphML; este adapter los
 * convierte a {@code double} durante la carga eager en el constructor.
 *
 * <p>Correspondencia de atributos OSMnx en GraphML:
 *
 * <ul>
 *   <li>Nodo: {@code y} = lat, {@code x} = lon (igual que Python: {@code datos["y"]}, {@code
 *       datos["x"]})
 *   <li>Arista: {@code length} = longitud en metros, {@code speed_kph} = velocidad efectiva en km/h
 * </ul>
 *
 * <p>Si una arista carece de {@code speed_kph} (atributo ausente o nulo en OSM), se aplica el
 * fallback {@link #MAXSPEED_FALLBACK_KMH}, igual que el Python. Si hay aristas paralelas entre los
 * mismos nodos, se conserva la de menor {@code longitudM}.
 *
 * <p>La carga es eager (constructor) y se cachea en {@code HashMap}. No se hace I/O en {@code
 * vecinos()} ni {@code coordenadas()}.
 */
public final class GrafoVialJGraphT implements GrafoVial {

  /**
   * Velocidad efectiva de fallback cuando {@code speed_kph} no está en la arista.
   *
   * <p>Replica {@code MAXSPEED_FALLBACK_KMH = 30.0} del Python.
   */
  static final double MAXSPEED_FALLBACK_KMH = 30.0;

  /** Mapa de nodo OSM → coordenadas (lat, lon). Cargado en el constructor. */
  private final Map<Long, Coordenadas> coordenadasPorNodo;

  /** Mapa de nodo OSM → lista de aristas salientes (deduplicated). Cargado en el constructor. */
  private final Map<Long, List<Arista>> adyacencia;

  /**
   * Construye el adapter a partir de un grafo JGraphT ya cargado con sus mapas de atributos.
   *
   * <p>Uso normal: {@link CargadorGrafo#cargarGrafoIvRegion(java.nio.file.Path)}.
   *
   * @param grafo grafo dirigido con pesos (JGraphT). Los nodos son Long (IDs OSM).
   * @param atributosNodos mapa nodo → (nombre_attr → valor_string) desde el GraphML
   * @param atributosAristas mapa arista → (nombre_attr → valor_string) desde el GraphML
   */
  GrafoVialJGraphT(
      DirectedWeightedPseudograph<Long, DefaultWeightedEdge> grafo,
      Map<Long, Map<String, String>> atributosNodos,
      Map<DefaultWeightedEdge, Map<String, String>> atributosAristas) {

    this.coordenadasPorNodo = new HashMap<>(grafo.vertexSet().size() * 2);
    this.adyacencia = new HashMap<>(grafo.vertexSet().size() * 2);

    // Parsear coordenadas de nodos: y=lat, x=lon (convencion OSMnx)
    for (Long nodoId : grafo.vertexSet()) {
      Map<String, String> attrs = atributosNodos.getOrDefault(nodoId, Collections.emptyMap());
      double lat = parseDoubleAttr(attrs, "y", Double.NaN);
      double lon = parseDoubleAttr(attrs, "x", Double.NaN);
      coordenadasPorNodo.put(nodoId, new Coordenadas(lat, lon));
      adyacencia.put(nodoId, new ArrayList<>());
    }

    // Parsear aristas, deduplicar conservando la de menor longitudM
    // Mapa temporal para deduplicacion: (origen, destino) -> Arista con menor longitud
    Map<Long, Map<Long, Arista>> mejorArista = new HashMap<>();

    for (DefaultWeightedEdge edge : grafo.edgeSet()) {
      Long origen = grafo.getEdgeSource(edge);
      Long destino = grafo.getEdgeTarget(edge);
      Map<String, String> attrs = atributosAristas.getOrDefault(edge, Collections.emptyMap());

      double longitudM = parseDoubleAttr(attrs, "length", Double.NaN);
      double velocidadKmh = parseDoubleAttr(attrs, "speed_kph", MAXSPEED_FALLBACK_KMH);

      Arista arista = new Arista(origen, destino, longitudM, velocidadKmh);

      mejorArista
          .computeIfAbsent(origen, k -> new HashMap<>())
          .merge(destino, arista, (a, b) -> a.longitudM() <= b.longitudM() ? a : b);
    }

    // Cargar en adyacencia
    for (Map.Entry<Long, Map<Long, Arista>> entry : mejorArista.entrySet()) {
      Long origen = entry.getKey();
      List<Arista> lista = adyacencia.get(origen);
      if (lista != null) {
        lista.addAll(entry.getValue().values());
      }
    }
  }

  // --------------------------------------------------------------------------
  // Implementacion de GrafoVial
  // --------------------------------------------------------------------------

  /** {@inheritDoc} */
  @Override
  public Coordenadas coordenadas(long nodo) {
    Coordenadas c = coordenadasPorNodo.get(nodo);
    if (c == null) {
      throw new IllegalArgumentException("Nodo no existe en el grafo: " + nodo);
    }
    return c;
  }

  /** {@inheritDoc} */
  @Override
  public List<Arista> vecinos(long nodo) {
    List<Arista> lista = adyacencia.get(nodo);
    if (lista == null) {
      return Collections.emptyList();
    }
    return Collections.unmodifiableList(lista);
  }

  /**
   * {@inheritDoc}
   *
   * <p>Brute-force haversine sobre todos los nodos. Para 16-20k nodos del bbox de Coquimbo el costo
   * es menor a 50 ms, aceptable antes del A*.
   */
  @Override
  public long nodoMasCercano(double lat, double lon) {
    long mejorNodo = -1;
    double mejorDistancia = Double.MAX_VALUE;

    for (Map.Entry<Long, Coordenadas> entry : coordenadasPorNodo.entrySet()) {
      Coordenadas c = entry.getValue();
      double distancia = haversineM(lat, lon, c.lat(), c.lon());
      if (distancia < mejorDistancia) {
        mejorDistancia = distancia;
        mejorNodo = entry.getKey();
      }
    }

    if (mejorNodo == -1) {
      throw new IllegalStateException("El grafo no contiene nodos.");
    }
    return mejorNodo;
  }

  /** {@inheritDoc} */
  @Override
  public Collection<Long> nodos() {
    return Collections.unmodifiableSet(coordenadasPorNodo.keySet());
  }

  // --------------------------------------------------------------------------
  // Metodos auxiliares privados
  // --------------------------------------------------------------------------

  /**
   * Calcula la distancia haversine entre dos puntos en metros.
   *
   * <p>Replica la funcion {@code haversine_m} del Python en {@code domain/routing/heuristica.py}.
   * Radio terrestre: 6_371_000 m.
   *
   * @param lat1 latitud del punto 1 en grados decimales
   * @param lon1 longitud del punto 1 en grados decimales
   * @param lat2 latitud del punto 2 en grados decimales
   * @param lon2 longitud del punto 2 en grados decimales
   * @return distancia en metros
   */
  static double haversineM(double lat1, double lon1, double lat2, double lon2) {
    final double R = 6_371_000.0;
    double dLat = Math.toRadians(lat2 - lat1);
    double dLon = Math.toRadians(lon2 - lon1);
    double a =
        Math.sin(dLat / 2) * Math.sin(dLat / 2)
            + Math.cos(Math.toRadians(lat1))
                * Math.cos(Math.toRadians(lat2))
                * Math.sin(dLon / 2)
                * Math.sin(dLon / 2);
    double c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
  }

  /**
   * Parsea un atributo String a double, retornando el default si el atributo es nulo, ausente o no
   * parseable.
   *
   * @param attrs mapa de atributos
   * @param clave nombre del atributo
   * @param defaultVal valor de retorno si el atributo no existe o no es parseable
   * @return valor parseado o default
   */
  private static double parseDoubleAttr(
      Map<String, String> attrs, String clave, double defaultVal) {
    String valor = attrs.get(clave);
    if (valor == null || valor.isBlank()) {
      return defaultVal;
    }
    try {
      return Double.parseDouble(valor);
    } catch (NumberFormatException e) {
      return defaultVal;
    }
  }
}
