package cl.ucen.sentinel.adapters.grafo;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.io.IOException;
import java.net.URL;
import java.nio.file.Path;
import java.nio.file.Paths;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

/**
 * Tests para {@link CargadorGrafo}.
 *
 * <p>Los tests marcados con {@code @Tag("integration")} cargan el GraphML real (21 MB, ~2s).
 */
class CargadorGrafoTest {

  // ==========================================================================
  // Tests NORMAL
  // ==========================================================================

  /** N-1: La carga del mini grafo retorna un GrafoVialJGraphT no nulo. */
  @Test
  void normal_carga_mini_grafo_retorna_instancia() throws IOException {
    Path path = rutaMiniGrafo();
    GrafoVialJGraphT grafo = CargadorGrafo.cargarGrafoIvRegion(path);
    assertThat(grafo).isNotNull();
  }

  /** N-2: El mini grafo cargado tiene exactamente 4 nodos y 3 aristas (post-dedup). */
  @Test
  void normal_carga_mini_grafo_nodos_y_aristas_correctos() throws IOException {
    GrafoVialJGraphT grafo = CargadorGrafo.cargarGrafoIvRegion(rutaMiniGrafo());
    assertThat(grafo.nodos()).hasSize(4);
    // Aristas: A->B (dedup: 750m), B->C (600m), C->A (1000m sin speed) = 3
    long totalAristas = grafo.nodos().stream().mapToLong(n -> grafo.vecinos(n).size()).sum();
    assertThat(totalAristas).isEqualTo(3L);
  }

  // ==========================================================================
  // Tests BORDE
  // ==========================================================================

  /**
   * B-1: Cargar dos veces el mismo archivo devuelve dos instancias independientes (no hay estado
   * compartido).
   */
  @Test
  void borde_doble_carga_devuelve_instancias_independientes() throws IOException {
    GrafoVialJGraphT grafo1 = CargadorGrafo.cargarGrafoIvRegion(rutaMiniGrafo());
    GrafoVialJGraphT grafo2 = CargadorGrafo.cargarGrafoIvRegion(rutaMiniGrafo());
    assertThat(grafo1).isNotSameAs(grafo2);
    assertThat(grafo1.nodos()).hasSameSizeAs(grafo2.nodos());
  }

  /**
   * B-2: Cargar un GraphML valido pero minimalista (un solo nodo, sin aristas) no lanza excepcion.
   */
  @Test
  void borde_grafo_sin_aristas_no_lanza_excepcion() throws IOException {
    // Usamos el nodo D del mini grafo que es aislado; el mini grafo tiene 4 nodos y se carga bien
    GrafoVialJGraphT grafo = CargadorGrafo.cargarGrafoIvRegion(rutaMiniGrafo());
    // Nodo D (100004) esta aislado
    assertThat(grafo.vecinos(100004L)).isEmpty();
  }

  // ==========================================================================
  // Tests ERROR
  // ==========================================================================

  /** E-1: Archivo inexistente lanza IOException. */
  @Test
  void error_archivo_inexistente_lanza_IOException() {
    Path noExiste = Paths.get("/tmp/no_existe_sentinel_dispatch_test.graphml");
    assertThatThrownBy(() -> CargadorGrafo.cargarGrafoIvRegion(noExiste))
        .isInstanceOf(IOException.class)
        .hasMessageContaining("no_existe_sentinel_dispatch_test.graphml");
  }

  /** E-2: Archivo XML que no es GraphML valido lanza IllegalStateException. */
  @Test
  void error_xml_no_graphml_lanza_IllegalStateException() {
    URL url =
        CargadorGrafoTest.class.getResource("/cl/ucen/sentinel/adapters/grafo/no_es_graphml.xml");
    assertThat(url).as("no_es_graphml.xml debe existir en resources de test").isNotNull();
    Path path = Paths.get(url.getPath());
    assertThatThrownBy(() -> CargadorGrafo.cargarGrafoIvRegion(path))
        .isInstanceOf(IllegalStateException.class);
  }

  // ==========================================================================
  // Tests REGLA DE NEGOCIO (RN)
  // ==========================================================================

  /**
   * RN-1: La velocidad de fallback es exactamente 30.0 km/h (replica MAXSPEED_FALLBACK_KMH del
   * Python).
   */
  @Test
  void rn_velocidad_fallback_es_30_kmh() {
    assertThat(GrafoVialJGraphT.MAXSPEED_FALLBACK_KMH).isEqualTo(30.0);
  }

  // ==========================================================================
  // Tests INTEGRATION
  // ==========================================================================

  /** IT-N1: El grafo real carga sin errores y tiene nodos. */
  @Test
  @Tag("integration")
  void integracion_carga_grafo_real_sin_errores() throws IOException {
    Path graphml =
        Paths.get(System.getProperty("user.dir"))
            .resolve("../data/graphs/coquimbo.graphml")
            .normalize();
    GrafoVialJGraphT grafo = CargadorGrafo.cargarGrafoIvRegion(graphml);
    assertThat(grafo).isNotNull();
    assertThat(grafo.nodos()).isNotEmpty();
  }

  // --------------------------------------------------------------------------
  // Helper
  // --------------------------------------------------------------------------

  private static Path rutaMiniGrafo() {
    URL url =
        CargadorGrafoTest.class.getResource("/cl/ucen/sentinel/adapters/grafo/mini_grafo.graphml");
    assertThat(url).as("mini_grafo.graphml debe existir").isNotNull();
    return Paths.get(url.getPath());
  }
}
