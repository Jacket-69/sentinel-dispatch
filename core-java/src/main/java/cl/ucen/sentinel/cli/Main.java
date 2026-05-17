package cl.ucen.sentinel.cli;

/**
 * Entry point del núcleo Java de Sentinel-Dispatch.
 *
 * <p>Versión inicial — sin lógica del dominio implementada. El árbol MPDS, el solver A* sobre
 * GraphML y la función de costo se agregan post-H2 según el roadmap del proyecto (ver ESTADO.md del
 * vault y ADR-0008).
 */
public final class Main {

  private Main() {}

  public static void main(final String[] args) {
    System.out.println(
        "sentinel-core-java 0.1.0 — esqueleto. Núcleo de cálculo pendiente (post-H2).");
  }
}
