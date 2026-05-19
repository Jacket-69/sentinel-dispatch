package cl.ucen.sentinel.domain.routing;

/**
 * No existe camino entre origen y destino en el grafo vial.
 *
 * <p>Espejo del Python {@code NoRutaDisponibleError} en {@code domain/routing/tipos.py}. Lanzada
 * por {@link AEstrella#aEstrella} cuando el destino no es alcanzable desde el origen. Casos
 * típicos: nodos en componentes disjuntos, destino fuera del bbox cargado, errores de snap.
 */
public class NoRutaDisponibleException extends RuntimeException {

  /**
   * Construye la excepción con un mensaje descriptivo que incluye los nodos origen y destino.
   *
   * @param origen identificador OSM del nodo de origen
   * @param destino identificador OSM del nodo de destino
   */
  public NoRutaDisponibleException(long origen, long destino) {
    super("sin ruta entre " + origen + " y " + destino);
  }
}
