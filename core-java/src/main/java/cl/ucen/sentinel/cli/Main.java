package cl.ucen.sentinel.cli;

import picocli.CommandLine;
import picocli.CommandLine.Command;

/**
 * Entry point del núcleo Java de Sentinel-Dispatch.
 *
 * <p>Dispatcher Picocli con subcomandos. Actualmente registra:
 *
 * <ul>
 *   <li>{@link RunDatasetCommand} — {@code run-dataset}: ejecuta el despacho sobre el dataset
 *       completo y emite un JSONL por incidente (schema ADR-0017, RT-02).
 * </ul>
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
 */
@Command(
    name = "sentinel-core-java",
    description = "Núcleo de cálculo Java de Sentinel-Dispatch.",
    subcommands = {RunDatasetCommand.class, CommandLine.HelpCommand.class},
    mixinStandardHelpOptions = true,
    version = "sentinel-core-java 0.1.0")
public final class Main {

  private Main() {}

  /**
   * Entry point principal. Delega a Picocli para el despacho de subcomandos.
   *
   * @param args argumentos de línea de comandos
   */
  public static void main(final String[] args) {
    int exitCode = new CommandLine(new Main()).execute(args);
    System.exit(exitCode);
  }
}
