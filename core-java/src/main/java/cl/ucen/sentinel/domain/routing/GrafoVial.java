package cl.ucen.sentinel.domain.routing;

import java.util.Collection;

/**
 * Puerto de solo lectura sobre el grafo vial cargado (ADR-0006, ADR-0010).
 *
 * <p>El módulo {@code domain.routing} depende únicamente de esta interfaz. Los adapters concretos
 * ({@code adapters.grafo.GrafoVialJGraphT}, fakes de test) la implementan. El A* puro recibe una
 * instancia {@code GrafoVial} y nada más.
 *
 * <p>Esta interfaz es un espejo del protocolo Python {@code GrafoVial} en {@code
 * domain/routing/grafo_vial.py}. Los identificadores de nodo son {@code long} porque los IDs OSM
 * son enteros de 64 bits.
 */
public interface GrafoVial {

  /**
   * Coordenadas geográficas de un nodo en grados decimales (EPSG:4326).
   *
   * @param nodo identificador OSM del nodo
   * @return coordenadas {@code (lat, lon)}. Para la conurbación La Serena-Coquimbo: lat en {@code
   *     [-30.5, -29.5]}, lon en {@code [-71.7, -70.5]}
   * @throws IllegalArgumentException si el nodo no existe en el grafo
   */
  Coordenadas coordenadas(long nodo);

  /**
   * Aristas salientes del nodo dado.
   *
   * <p>Idempotente y sin I/O en cada llamada (el adapter cachea en el constructor). El A* itera
   * sobre el resultado en cada expansión.
   *
   * @param nodo identificador OSM del nodo
   * @return lista de aristas salientes; vacía si el nodo no tiene vecinos
   */
  java.util.List<Arista> vecinos(long nodo);

  /**
   * Snap de una coordenada arbitraria al nodo OSM más cercano (brute-force haversine).
   *
   * <p>Para 16-20k nodos del bbox de Coquimbo el costo es menor a 50 ms por snap. Aplicado en el
   * borde de entrada antes de invocar el A*.
   *
   * @param lat latitud en grados decimales
   * @param lon longitud en grados decimales
   * @return identificador OSM del nodo más cercano
   */
  long nodoMasCercano(double lat, double lon);

  /**
   * Colección de todos los identificadores de nodo del grafo.
   *
   * @return colección inmutable de IDs OSM
   */
  Collection<Long> nodos();

  // --------------------------------------------------------------------------
  // Tipos de datos del dominio (records Java 21 — inmutables, sin dependencias
  // externas)
  // --------------------------------------------------------------------------

  /**
   * Coordenadas geográficas en EPSG:4326.
   *
   * @param lat latitud en grados decimales
   * @param lon longitud en grados decimales
   */
  record Coordenadas(double lat, double lon) {}

  /**
   * Atributos de una arista del grafo vial relevantes para el A*.
   *
   * <p>Espejo del dataclass Python {@code Arista} en {@code domain/routing/tipos.py}. Los valores
   * de {@code velocidadEfectivaKmh} son el resultado del cascade descrito en ADR-0010 §2 (tag
   * {@code maxspeed} de OSM si existe; sino default por {@code highway} type según tabla Chile). El
   * dominio no convierte unidades hasta el cálculo de peso.
   *
   * @param origen nodo del que sale la arista
   * @param destino nodo al que llega la arista
   * @param longitudM largo del segmento en metros
   * @param velocidadEfectivaKmh velocidad nominal en km/h, ya resuelta por el cascade
   */
  record Arista(long origen, long destino, double longitudM, double velocidadEfectivaKmh) {}
}
