package cl.ucen.sentinel.cli;

import cl.ucen.sentinel.adapters.grafo.CargadorGrafo;
import cl.ucen.sentinel.adapters.grafo.GrafoVialJGraphT;
import cl.ucen.sentinel.application.DespacharAmbulancia;
import cl.ucen.sentinel.application.ResultadoDespacho;
import cl.ucen.sentinel.domain.dispatch.EstadoUnidad;
import cl.ucen.sentinel.domain.dispatch.Incidente;
import cl.ucen.sentinel.domain.dispatch.TipoUnidad;
import cl.ucen.sentinel.domain.dispatch.Unidad;
import cl.ucen.sentinel.domain.triaje.CategoriaMPDS;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Callable;
import picocli.CommandLine.Command;
import picocli.CommandLine.Option;

/**
 * Subcomando {@code run-dataset} del CLI de Sentinel-Dispatch (Java).
 *
 * <p>Espejo del Python {@code sentinel run-dataset} ({@code run_dataset_cmd.py}). Lee el dataset
 * JSON de incidentes y el JSON de unidades, ejecuta el caso de uso {@link
 * DespacharAmbulancia#despachar} por cada incidente y emite un archivo JSONL por incidente en el
 * directorio de salida, siguiendo el schema congelado en ADR-0017.
 *
 * <p>Uso:
 *
 * <pre>{@code
 * java -cp ... cl.ucen.sentinel.cli.Main run-dataset \
 *   --in  data/dataset/incidentes.json \
 *   --unidades data/dataset/unidades.json \
 *   --graph data/graphs/coquimbo.graphml \
 *   --out /tmp/java-out/
 * }</pre>
 *
 * <p>Exit codes:
 *
 * <ul>
 *   <li><b>0</b>: todos los incidentes procesados sin error.
 *   <li><b>1</b>: error inesperado durante el procesamiento.
 *   <li><b>2</b>: archivo de entrada no encontrado o JSON inválido.
 * </ul>
 */
@Command(
    name = "run-dataset",
    description =
        "Ejecuta el despacho sobre el dataset completo y emite un JSONL por incidente"
            + " (schema ADR-0017).",
    mixinStandardHelpOptions = true)
public class RunDatasetCommand implements Callable<Integer> {

  /** Path por defecto para el JSON de incidentes (relativo a la raíz del monorepo). */
  private static final String DEFAULT_INCIDENTES = "../data/dataset/incidentes.json";

  /** Path por defecto para el JSON de unidades. */
  private static final String DEFAULT_UNIDADES = "../data/dataset/unidades.json";

  /** Path por defecto para el GraphML del grafo vial. */
  private static final String DEFAULT_GRAPH = "../data/graphs/coquimbo.graphml";

  @Option(
      names = "--in",
      description = "Path al JSON con los incidentes del dataset.",
      defaultValue = DEFAULT_INCIDENTES)
  private Path incidentesPath;

  @Option(
      names = "--unidades",
      description = "Path al JSON con la flota de unidades.",
      defaultValue = DEFAULT_UNIDADES)
  private Path unidadesPath;

  @Option(
      names = "--graph",
      description = "Path al GraphML del grafo vial.",
      defaultValue = DEFAULT_GRAPH)
  private Path graphPath;

  @Option(
      names = "--out",
      description = "Directorio de salida para los archivos JSONL (se crea si no existe).",
      defaultValue = "out")
  private Path outDir;

  private static final ObjectMapper MAPPER = new ObjectMapper();

  @Override
  public Integer call() {
    // Validar existencia de archivos de entrada
    if (!Files.exists(incidentesPath)) {
      System.err.println(
          "Error: archivo de incidentes no encontrado: " + incidentesPath.toAbsolutePath());
      return 2;
    }
    if (!Files.exists(unidadesPath)) {
      System.err.println(
          "Error: archivo de unidades no encontrado: " + unidadesPath.toAbsolutePath());
      return 2;
    }
    if (!Files.exists(graphPath)) {
      System.err.println("Error: archivo de grafo no encontrado: " + graphPath.toAbsolutePath());
      return 2;
    }

    // Parsear JSON de entrada
    List<Map<String, Object>> incidentesRaw;
    List<Map<String, Object>> unidadesRaw;
    try {
      incidentesRaw =
          MAPPER.readValue(
              incidentesPath.toFile(), new TypeReference<List<Map<String, Object>>>() {});
    } catch (IOException e) {
      System.err.println("Error: incidentes JSON inválido — " + e.getMessage());
      return 2;
    }
    try {
      unidadesRaw =
          MAPPER.readValue(
              unidadesPath.toFile(), new TypeReference<List<Map<String, Object>>>() {});
    } catch (IOException e) {
      System.err.println("Error: unidades JSON inválido — " + e.getMessage());
      return 2;
    }

    // Preparar directorio de salida
    try {
      Files.createDirectories(outDir);
    } catch (IOException e) {
      System.err.println("Error: no se pudo crear directorio de salida: " + e.getMessage());
      return 1;
    }

    if (incidentesRaw.isEmpty()) {
      System.out.println("Dataset vacío; no se generaron archivos de salida.");
      return 0;
    }

    // Cargar grafo
    GrafoVialJGraphT grafo;
    try {
      grafo = CargadorGrafo.cargarGrafoIvRegion(graphPath);
    } catch (IOException | IllegalStateException e) {
      System.err.println("Error al cargar grafo: " + e.getMessage());
      return 1;
    }

    // Construir flota
    List<Unidad> flota;
    try {
      flota =
          unidadesRaw.stream()
              .map(RunDatasetCommand::unidadDesdeMap)
              .collect(java.util.stream.Collectors.toList());
    } catch (IllegalArgumentException e) {
      System.err.println("Error al parsear unidades: " + e.getMessage());
      return 2;
    }

    // Procesar cada incidente
    int procesados = 0;
    for (Map<String, Object> raw : incidentesRaw) {
      Incidente incidente;
      try {
        incidente = incidenteDesdeMap(raw);
      } catch (IllegalArgumentException e) {
        System.err.println("Error al parsear incidente: " + e.getMessage());
        return 2;
      }

      ResultadoDespacho resultado = DespacharAmbulancia.despachar(incidente, flota, grafo);
      String linea = JsonlSerializer.serializar(resultado);

      Path outFile = outDir.resolve(incidente.id() + ".jsonl");
      try {
        Files.writeString(outFile, linea + "\n", StandardCharsets.UTF_8);
      } catch (IOException e) {
        System.err.println("Error al escribir " + outFile + ": " + e.getMessage());
        return 1;
      }
      procesados++;
    }

    System.out.println(
        "Procesados " + procesados + " incidente(s). Salida en: " + outDir.toAbsolutePath());
    return 0;
  }

  // ---------------------------------------------------------------------------
  // Helpers de construcción de DTOs desde Map (JSON parseado por Jackson)
  // ---------------------------------------------------------------------------

  /**
   * Construye una {@link Unidad} a partir del mapa parseado de {@code unidades.json}.
   *
   * @param data mapa con los campos de la unidad
   * @return instancia de {@link Unidad}
   * @throws IllegalArgumentException si algún campo tiene valor inválido
   */
  static Unidad unidadDesdeMap(Map<String, Object> data) {
    String id = (String) data.get("id");
    String patente = (String) data.get("patente");
    TipoUnidad tipo = TipoUnidad.fromValor((String) data.get("tipo"));
    String baseNombre = (String) data.get("base_nombre");
    double baseLat = ((Number) data.get("base_lat")).doubleValue();
    double baseLon = ((Number) data.get("base_lon")).doubleValue();
    EstadoUnidad estado = EstadoUnidad.fromValor((String) data.get("estado"));
    return new Unidad(id, patente, tipo, baseNombre, baseLat, baseLon, estado);
  }

  /**
   * Construye un {@link Incidente} a partir del mapa parseado de {@code incidentes.json}.
   *
   * <p>La categoría MPDS se deriva del campo {@code ground_truth.categoria_mpds} (ya clasificado en
   * el dataset de aceptación). El timestamp se toma de {@code timestamp}.
   *
   * @param data mapa con los campos del incidente
   * @return instancia de {@link Incidente}
   * @throws IllegalArgumentException si algún campo tiene valor inválido
   */
  @SuppressWarnings("unchecked")
  static Incidente incidenteDesdeMap(Map<String, Object> data) {
    String id = (String) data.get("id");
    double lat = ((Number) data.get("lat")).doubleValue();
    double lon = ((Number) data.get("lon")).doubleValue();
    String timestamp = (String) data.get("timestamp");
    Map<String, Object> groundTruth = (Map<String, Object>) data.get("ground_truth");
    CategoriaMPDS categoria = CategoriaMPDS.fromValor((String) groundTruth.get("categoria_mpds"));
    return new Incidente(id, lat, lon, categoria, timestamp);
  }
}
