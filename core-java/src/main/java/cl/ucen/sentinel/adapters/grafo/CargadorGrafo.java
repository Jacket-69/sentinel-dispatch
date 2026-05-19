package cl.ucen.sentinel.adapters.grafo;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;
import java.util.logging.Logger;
import org.jgrapht.graph.DefaultWeightedEdge;
import org.jgrapht.graph.DirectedWeightedPseudograph;
import org.jgrapht.nio.ImportException;
import org.jgrapht.nio.graphml.GraphMLImporter;

/**
 * Factory de carga del grafo vial desde GraphML generado por OSMnx.
 *
 * <p>Encapsula el ciclo de vida del {@code GraphMLImporter} de JGraphT y el parseo de atributos
 * OSMnx (todos son {@code attr.type="string"} en el GraphML). Produce un {@link GrafoVialJGraphT}
 * con carga eager.
 */
public final class CargadorGrafo {

  private static final Logger LOG = Logger.getLogger(CargadorGrafo.class.getName());

  private CargadorGrafo() {
    // Factory estatica, no instanciar
  }

  /**
   * Carga el grafo vial de la IV Region desde un archivo GraphML generado por OSMnx.
   *
   * <p>OSMnx serializa todos los atributos como {@code attr.type="string"}, incluyendo coordenadas
   * numéricas ({@code x}, {@code y}) y métricas de arista ({@code length}, {@code speed_kph}). El
   * importer JGraphT lee el XML correctamente; los hooks de atributo convierten los Strings a
   * {@code double} durante la carga.
   *
   * @param graphml ruta al archivo {@code .graphml}
   * @return instancia de {@link GrafoVialJGraphT} con carga completa
   * @throws IOException si el archivo no existe o no se puede leer
   * @throws IllegalStateException si el GraphML está malformado o no es un grafo válido
   */
  public static GrafoVialJGraphT cargarGrafoIvRegion(Path graphml)
      throws IOException, IllegalStateException {

    if (!Files.exists(graphml)) {
      throw new IOException("Archivo GraphML no encontrado: " + graphml.toAbsolutePath());
    }

    LOG.info(() -> "Cargando grafo desde: " + graphml.toAbsolutePath());

    // Mapas de atributos para nodos y aristas (se llenan via hooks del importer)
    Map<Long, Map<String, String>> atributosNodos = new HashMap<>();
    Map<DefaultWeightedEdge, Map<String, String>> atributosAristas = new HashMap<>();

    // Grafo dirigido con pesos; se usa Pseudograph para tolerar self-loops que OSMnx puede
    // generar en grafos simplificados (169 self-loops en coquimbo.graphml). El Pseudograph
    // permite tanto loops como aristas paralelas entre los mismos nodos.
    DirectedWeightedPseudograph<Long, DefaultWeightedEdge> grafo =
        new DirectedWeightedPseudograph<>(DefaultWeightedEdge.class);

    GraphMLImporter<Long, DefaultWeightedEdge> importer = new GraphMLImporter<>();

    // OSMnx genera GraphML con IDs de arista duplicados (id="0" para todas las aristas en
    // cada nodo origen). El schema GraphML estricto lo rechaza; se desactiva la validacion.
    importer.setSchemaValidation(false);

    // Proveedor de vertices: convertir el ID string del GraphML a Long
    importer.setVertexFactory(id -> Long.parseLong(id));

    // Hook de atributos de nodo: acumular en el mapa
    importer.addVertexAttributeConsumer(
        (par, atributo) -> {
          Long nodoId = par.getFirst();
          String nombreAttr = par.getSecond();
          atributosNodos
              .computeIfAbsent(nodoId, k -> new HashMap<>())
              .put(nombreAttr, atributo.getValue());
        });

    // Hook de atributos de arista: acumular en el mapa
    importer.addEdgeAttributeConsumer(
        (par, atributo) -> {
          DefaultWeightedEdge arista = par.getFirst();
          String nombreAttr = par.getSecond();
          atributosAristas
              .computeIfAbsent(arista, k -> new HashMap<>())
              .put(nombreAttr, atributo.getValue());
        });

    try (InputStream is = Files.newInputStream(graphml)) {
      importer.importGraph(grafo, is);
    } catch (ImportException e) {
      throw new IllegalStateException(
          "GraphML malformado o no parseable: " + graphml.toAbsolutePath(), e);
    }

    int nNodos = grafo.vertexSet().size();
    int nAristas = grafo.edgeSet().size();
    LOG.info(() -> "Grafo cargado: " + nNodos + " nodos, " + nAristas + " aristas");

    return new GrafoVialJGraphT(grafo, atributosNodos, atributosAristas);
  }
}
