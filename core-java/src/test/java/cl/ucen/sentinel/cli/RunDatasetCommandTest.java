package cl.ucen.sentinel.cli;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import picocli.CommandLine;

/**
 * Tests de integración del subcomando {@code run-dataset} usando el grafo sintético de tests.
 *
 * <p>Se usa {@code mini_grafo_cli.graphml} (4 nodos, 7 aristas) para que la suite sea rápida y
 * determinista sin necesidad del grafo real (21 MB). El A* encuentra rutas dentro del mini-grafo.
 *
 * <p>Taxonomía:
 *
 * <ul>
 *   <li>Normal: 1 incidente Alpha + flota → produce JSONL con schema completo.
 *   <li>Borde: directorio de salida inexistente → se crea automáticamente.
 *   <li>Error: archivo de incidentes inexistente → exit 2.
 * </ul>
 */
class RunDatasetCommandTest {

  private static final ObjectMapper MAPPER = new ObjectMapper();

  // ---------------------------------------------------------------------------
  // Fixtures JSON mínimos
  // ---------------------------------------------------------------------------

  /** Incidente cerca de los nodos del mini_grafo_cli.graphml. */
  private static final String INCIDENTE_ALPHA_JSON =
      "[{"
          + "\"id\":\"I-T1\","
          + "\"lat\":-29.9100,"
          + "\"lon\":-71.2563,"
          + "\"timestamp\":\"2026-05-25T08:15:00-04:00\","
          + "\"respuestas_triaje\":{"
          + "\"consciente\":true,\"respira_normal\":true,\"sangrado\":\"Ninguno\","
          + "\"dolor_toracico\":\"Ninguno\",\"dificultad_respiratoria\":false,"
          + "\"grupo_etario\":\"Adulto\""
          + "},"
          + "\"ground_truth\":{"
          + "\"categoria_mpds\":\"Alpha\",\"unidad_esperada\":\"U01\","
          + "\"eta_aprox_min\":1,\"regla_aplicada\":9,\"nota\":\"Test.\""
          + "}"
          + "}]";

  /** Flota con solo 1 Avanzada disponible. */
  private static final String UNIDADES_UNA_AVANZADA_JSON =
      "[{"
          + "\"id\":\"U01\",\"patente\":\"AMB-001\",\"tipo\":\"Avanzada\","
          + "\"base_nombre\":\"Hospital Test\","
          + "\"base_lat\":-29.9077,\"base_lon\":-71.2535,"
          + "\"estado\":\"Disponible\""
          + "}]";

  // ---------------------------------------------------------------------------
  // Helper
  // ---------------------------------------------------------------------------

  /** Devuelve la ruta al mini grafo de tests del CLI. */
  private Path rutaMiniGrafo() {
    URL url =
        getClass().getClassLoader().getResource("cl/ucen/sentinel/cli/mini_grafo_cli.graphml");
    assertThat(url).as("mini_grafo_cli.graphml no encontrado en resources de test").isNotNull();
    return Paths.get(url.getPath());
  }

  /** Escribe un string como archivo UTF-8 y devuelve el path. */
  private Path writeFile(Path dir, String name, String content) throws IOException {
    Path file = dir.resolve(name);
    Files.writeString(file, content, StandardCharsets.UTF_8);
    return file;
  }

  /** Parsea un archivo {@code .jsonl} (una línea) a {@link Map}. */
  @SuppressWarnings("unchecked")
  private Map<String, Object> parseJsonl(Path file) throws IOException {
    String line = Files.readString(file, StandardCharsets.UTF_8).strip();
    return MAPPER.readValue(line, new TypeReference<Map<String, Object>>() {});
  }

  // ---------------------------------------------------------------------------
  // Normal-1: 1 incidente Alpha + Avanzada disponible → JSONL con schema
  // ---------------------------------------------------------------------------

  @Test
  void normal1_unIncidenteAlphaProduceJsonlConSchemaCompleto(@TempDir Path tmp) throws IOException {
    Path incFile = writeFile(tmp, "inc.json", INCIDENTE_ALPHA_JSON);
    Path unidadesFile = writeFile(tmp, "unidades.json", UNIDADES_UNA_AVANZADA_JSON);
    Path outDir = tmp.resolve("out");
    Path grafoPath = rutaMiniGrafo();

    int exit =
        new CommandLine(new RunDatasetCommand())
            .execute(
                "--in",
                incFile.toString(),
                "--unidades",
                unidadesFile.toString(),
                "--graph",
                grafoPath.toString(),
                "--out",
                outDir.toString());

    assertThat(exit).isEqualTo(0);
    Path jsonlFile = outDir.resolve("I-T1.jsonl");
    assertThat(jsonlFile).exists();

    Map<String, Object> doc = parseJsonl(jsonlFile);
    assertThat(doc.get("incidente_id")).isEqualTo("I-T1");
    assertThat(doc.get("categoria_mpds")).isEqualTo("Alpha");
    assertThat(doc.get("despacho_suboptimo")).isEqualTo(false);
    assertThat(doc).containsKey("eta_segundos");
    assertThat(doc).containsKey("costo");
    assertThat(doc).containsKey("ruta");

    // Los IDs de nodo en ruta deben ser strings
    @SuppressWarnings("unchecked")
    List<String> ruta = (List<String>) doc.get("ruta");
    assertThat(ruta).allSatisfy(n -> assertThat(n).isInstanceOf(String.class));
  }

  // ---------------------------------------------------------------------------
  // Borde-1: directorio de salida inexistente → se crea
  // ---------------------------------------------------------------------------

  @Test
  void borde1_directorioSalidaInexistenteSeCrea(@TempDir Path tmp) throws IOException {
    Path incFile = writeFile(tmp, "inc.json", INCIDENTE_ALPHA_JSON);
    Path unidadesFile = writeFile(tmp, "unidades.json", UNIDADES_UNA_AVANZADA_JSON);
    Path outDir = tmp.resolve("nuevo").resolve("subdir").resolve("salida");
    assertThat(outDir).doesNotExist();

    int exit =
        new CommandLine(new RunDatasetCommand())
            .execute(
                "--in",
                incFile.toString(),
                "--unidades",
                unidadesFile.toString(),
                "--graph",
                rutaMiniGrafo().toString(),
                "--out",
                outDir.toString());

    assertThat(exit).isEqualTo(0);
    assertThat(outDir).isDirectory();
    assertThat(outDir.resolve("I-T1.jsonl")).exists();
  }

  // ---------------------------------------------------------------------------
  // Error-1: archivo de incidentes inexistente → exit 2
  // ---------------------------------------------------------------------------

  @Test
  void error1_incidentesInexistenteExit2(@TempDir Path tmp) throws IOException {
    Path unidadesFile = writeFile(tmp, "unidades.json", UNIDADES_UNA_AVANZADA_JSON);

    int exit =
        new CommandLine(new RunDatasetCommand())
            .execute(
                "--in",
                tmp.resolve("no_existe.json").toString(),
                "--unidades",
                unidadesFile.toString(),
                "--graph",
                rutaMiniGrafo().toString(),
                "--out",
                tmp.resolve("out").toString());

    assertThat(exit).isEqualTo(2);
  }
}
