package cl.ucen.sentinel.adapters.grafo;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.within;

import cl.ucen.sentinel.domain.routing.GrafoVial;
import java.io.IOException;
import java.net.URL;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

/**
 * Tests para {@link GrafoVialJGraphT}.
 *
 * <p>Los tests marcados con {@code @Tag("integration")} cargan el GraphML real (21 MB, ~2s). La
 * suite default los incluye. Los tests sin tag usan el mini grafo embebido en recursos de test.
 */
class GrafoVialJGraphTTest {

  private static GrafoVialJGraphT grafoMini;

  // Ground truth obtenido del adapter Python el 2026-05-19:
  // uv run --project core-python python -c "..."
  // Puntos: bases SAMU de unidades.json
  static final long GT_NODO_HOSPITAL_SAN_JUAN = 297117252L;
  static final double GT_LAT_HOSPITAL_SAN_JUAN = -29.9078903;
  static final double GT_LON_HOSPITAL_SAN_JUAN = -71.2534694;

  static final long GT_NODO_CESFAM_PEDRO_AGUIRRE = 989536304L;
  static final double GT_LAT_CESFAM_PEDRO_AGUIRRE = -29.9011684;
  static final double GT_LON_CESFAM_PEDRO_AGUIRRE = -71.2439547;

  static final long GT_NODO_HOSPITAL_SAN_PABLO = 1064753516L;
  static final double GT_LAT_HOSPITAL_SAN_PABLO = -29.9529909;
  static final double GT_LON_HOSPITAL_SAN_PABLO = -71.3390875;

  static final long GT_NODO_CESFAM_LAS_COMPANIAS = 7389926280L;
  static final double GT_LAT_CESFAM_LAS_COMPANIAS = -29.8867618;
  static final double GT_LON_CESFAM_LAS_COMPANIAS = -71.2544174;

  static final long GT_NODO_CESFAM_TIERRAS_BLANCAS = 1054581612L;
  static final double GT_LAT_CESFAM_TIERRAS_BLANCAS = -29.9605998;
  static final double GT_LON_CESFAM_TIERRAS_BLANCAS = -71.3197106;

  @BeforeAll
  static void cargarMiniGrafo() throws IOException {
    URL url =
        GrafoVialJGraphTTest.class.getResource(
            "/cl/ucen/sentinel/adapters/grafo/mini_grafo.graphml");
    assertThat(url).as("mini_grafo.graphml debe existir en resources de test").isNotNull();
    grafoMini = CargadorGrafo.cargarGrafoIvRegion(Paths.get(url.getPath()));
  }

  // ==========================================================================
  // Tests NORMAL
  // ==========================================================================

  /** N-1: El mini grafo carga 4 nodos correctamente. */
  @Test
  void normal_carga_numero_nodos() {
    assertThat(grafoMini.nodos()).hasSize(4);
  }

  /** N-2: coordenadas() devuelve lat y lon correctos para el nodo A del mini grafo. */
  @Test
  void normal_coordenadas_nodo_existente() {
    GrafoVial.Coordenadas c = grafoMini.coordenadas(100001L);
    assertThat(c.lat()).isCloseTo(-29.9077, within(1e-6));
    assertThat(c.lon()).isCloseTo(-71.2535, within(1e-6));
  }

  /**
   * N-3: vecinos() devuelve aristas salientes del nodo A (deduplicado: solo la de menor longitud).
   */
  @Test
  void normal_vecinos_nodo_con_aristas() {
    List<GrafoVial.Arista> vecinos = grafoMini.vecinos(100001L);
    // Nodo A tiene dos aristas A->B (750m y 900m); debe conservarse la de 750m
    assertThat(vecinos).hasSize(1);
    GrafoVial.Arista arista = vecinos.get(0);
    assertThat(arista.origen()).isEqualTo(100001L);
    assertThat(arista.destino()).isEqualTo(100002L);
    assertThat(arista.longitudM()).isCloseTo(750.0, within(1e-6));
    assertThat(arista.velocidadEfectivaKmh()).isCloseTo(50.0, within(1e-6));
  }

  /** N-4: nodoMasCercano() retorna el nodo correcto para coordenadas exactas del nodo A. */
  @Test
  void normal_nodoMasCercano_coordenadas_exactas() {
    long nodo = grafoMini.nodoMasCercano(-29.9077, -71.2535);
    assertThat(nodo).isEqualTo(100001L);
  }

  /** N-5: nodoMasCercano() retorna el nodo B para coordenadas cercanas a B. */
  @Test
  void normal_nodoMasCercano_punto_proximo() {
    // Punto levemente desplazado desde el nodo B (100002)
    long nodo = grafoMini.nodoMasCercano(-29.9101, -71.2601);
    assertThat(nodo).isEqualTo(100002L);
  }

  /** N-6: arista sin speed_kph usa el fallback de 30 km/h. */
  @Test
  void normal_arista_sin_speed_usa_fallback() {
    // Nodo C (100003) tiene arista C->A sin speed_kph
    List<GrafoVial.Arista> vecinos = grafoMini.vecinos(100003L);
    assertThat(vecinos).hasSize(1);
    assertThat(vecinos.get(0).velocidadEfectivaKmh())
        .isCloseTo(GrafoVialJGraphT.MAXSPEED_FALLBACK_KMH, within(1e-6));
  }

  // ==========================================================================
  // Tests BORDE
  // ==========================================================================

  /** B-1: nodo aislado (sin aristas salientes) -> vecinos() devuelve lista vacia. */
  @Test
  void borde_vecinos_nodo_aislado() {
    List<GrafoVial.Arista> vecinos = grafoMini.vecinos(100004L);
    assertThat(vecinos).isEmpty();
  }

  /**
   * B-2: nodoMasCercano() con coordenadas muy lejos del bbox devuelve el nodo del borde mas proximo
   * (no lanza excepcion).
   */
  @Test
  void borde_nodoMasCercano_coordenadas_lejanas() {
    // Punto en el Atlantico — muy lejos; debe devolver algun nodo sin fallar
    long nodo = grafoMini.nodoMasCercano(0.0, 0.0);
    assertThat(grafoMini.nodos()).contains(nodo);
  }

  // ==========================================================================
  // Tests ERROR
  // ==========================================================================

  /** E-1: coordenadas() con nodo inexistente lanza IllegalArgumentException. */
  @Test
  void error_coordenadas_nodo_inexistente() {
    assertThatThrownBy(() -> grafoMini.coordenadas(999999L))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("999999");
  }

  /** E-2: vecinos() con nodo inexistente devuelve lista vacia (no lanza excepcion). */
  @Test
  void error_vecinos_nodo_inexistente_devuelve_vacio() {
    // El adapter no falla para nodos desconocidos en vecinos() — retorna vacio
    List<GrafoVial.Arista> vecinos = grafoMini.vecinos(999999L);
    assertThat(vecinos).isEmpty();
  }

  // ==========================================================================
  // Tests REGLA DE NEGOCIO (RN)
  // ==========================================================================

  /**
   * RN-1: Las velocidades efectivas en aristas se exponen tal como las trae el GraphML (en km/h,
   * sin conversion a m/s ni factor adicional).
   */
  @Test
  void rn_velocidad_expuesta_sin_conversion() {
    // Arista B->C tiene speed_kph=40.0 en el GraphML
    List<GrafoVial.Arista> vecinos = grafoMini.vecinos(100002L);
    assertThat(vecinos).hasSize(1);
    GrafoVial.Arista arista = vecinos.get(0);
    assertThat(arista.destino()).isEqualTo(100003L);
    // El valor debe ser exactamente 40.0 km/h, no convertido
    assertThat(arista.velocidadEfectivaKmh()).isCloseTo(40.0, within(1e-9));
  }

  // ==========================================================================
  // Tests INTEGRATION (cargan el GraphML real de 21 MB)
  // ==========================================================================

  /**
   * IT-N1: El grafo real tiene exactamente 16679 nodos y 42107 aristas deduplicadas.
   *
   * <p>Ground truth Python (2026-05-19): Nodos: 16679, Aristas totales: 42508 (con paralelas).
   * Aristas unicas (pares origen→destino distintos, deduplicado igual que Java): 42107. El adapter
   * Python es un MultiDiGraph que conserva todas las aristas paralelas; Java conserva solo la de
   * menor longitud por par (origen, destino). Ambos coinciden en pares unicos: 42107.
   */
  @Test
  @Tag("integration")
  void integracion_conteo_nodos_y_aristas_paridad_python() throws IOException {
    GrafoVialJGraphT grafoReal = cargarGrafoReal();
    assertThat(grafoReal.nodos()).as("numero de nodos debe coincidir con Python").hasSize(16679);

    // Conteo de aristas post-deduplicacion: pares (origen, destino) unicos.
    // Python aristas unicas: 42107. Java deduplica paralelas en el constructor -> 42107.
    long totalAristas =
        grafoReal.nodos().stream().mapToLong(n -> grafoReal.vecinos(n).size()).sum();
    assertThat(totalAristas)
        .as("aristas deduplicadas (pares origen→destino unicos) deben ser 42107")
        .isEqualTo(42107L);
  }

  /**
   * IT-N2: nodoMasCercano() para Hospital San Juan de Dios La Serena coincide con Python.
   *
   * <p>Punto: (-29.9077, -71.2535). Python devuelve nodo 297117252.
   */
  @Test
  @Tag("integration")
  void integracion_paridad_nodoMasCercano_hospital_san_juan() throws IOException {
    GrafoVialJGraphT grafoReal = cargarGrafoReal();
    long nodo = grafoReal.nodoMasCercano(-29.9077, -71.2535);
    assertThat(nodo)
        .as("nodo mas cercano a Hospital San Juan debe coincidir con Python")
        .isEqualTo(GT_NODO_HOSPITAL_SAN_JUAN);

    GrafoVial.Coordenadas c = grafoReal.coordenadas(nodo);
    assertThat(c.lat()).isCloseTo(GT_LAT_HOSPITAL_SAN_JUAN, within(1e-6));
    assertThat(c.lon()).isCloseTo(GT_LON_HOSPITAL_SAN_JUAN, within(1e-6));
  }

  /**
   * IT-N3: nodoMasCercano() para CESFAM Pedro Aguirre Cerda coincide con Python.
   *
   * <p>Punto: (-29.9015, -71.2433). Python devuelve nodo 989536304.
   */
  @Test
  @Tag("integration")
  void integracion_paridad_nodoMasCercano_cesfam_pedro_aguirre() throws IOException {
    GrafoVialJGraphT grafoReal = cargarGrafoReal();
    long nodo = grafoReal.nodoMasCercano(-29.9015, -71.2433);
    assertThat(nodo)
        .as("nodo mas cercano a CESFAM Pedro Aguirre Cerda debe coincidir con Python")
        .isEqualTo(GT_NODO_CESFAM_PEDRO_AGUIRRE);
  }

  /**
   * IT-N4: nodoMasCercano() para Hospital San Pablo de Coquimbo coincide con Python.
   *
   * <p>Punto: (-29.9533, -71.3389). Python devuelve nodo 1064753516.
   */
  @Test
  @Tag("integration")
  void integracion_paridad_nodoMasCercano_hospital_san_pablo_coquimbo() throws IOException {
    GrafoVialJGraphT grafoReal = cargarGrafoReal();
    long nodo = grafoReal.nodoMasCercano(-29.9533, -71.3389);
    assertThat(nodo)
        .as("nodo mas cercano a Hospital San Pablo de Coquimbo debe coincidir con Python")
        .isEqualTo(GT_NODO_HOSPITAL_SAN_PABLO);
  }

  /**
   * IT-N5: nodoMasCercano() para CESFAM Las Compañias coincide con Python.
   *
   * <p>Punto: (-29.8868, -71.2548). Python devuelve nodo 7389926280.
   */
  @Test
  @Tag("integration")
  void integracion_paridad_nodoMasCercano_cesfam_las_companias() throws IOException {
    GrafoVialJGraphT grafoReal = cargarGrafoReal();
    long nodo = grafoReal.nodoMasCercano(-29.8868, -71.2548);
    assertThat(nodo)
        .as("nodo mas cercano a CESFAM Las Companias debe coincidir con Python")
        .isEqualTo(GT_NODO_CESFAM_LAS_COMPANIAS);
  }

  /**
   * IT-N6: nodoMasCercano() para CESFAM Tierras Blancas coincide con Python.
   *
   * <p>Punto: (-29.9622, -71.3198). Python devuelve nodo 1054581612.
   */
  @Test
  @Tag("integration")
  void integracion_paridad_nodoMasCercano_cesfam_tierras_blancas() throws IOException {
    GrafoVialJGraphT grafoReal = cargarGrafoReal();
    long nodo = grafoReal.nodoMasCercano(-29.9622, -71.3198);
    assertThat(nodo)
        .as("nodo mas cercano a CESFAM Tierras Blancas debe coincidir con Python")
        .isEqualTo(GT_NODO_CESFAM_TIERRAS_BLANCAS);
  }

  /** IT-B1: coordenadas() del nodo snapeado tiene lat en rango IV Region. */
  @Test
  @Tag("integration")
  void integracion_borde_coordenadas_en_rango_iv_region() throws IOException {
    GrafoVialJGraphT grafoReal = cargarGrafoReal();
    long nodo = grafoReal.nodoMasCercano(-29.9077, -71.2535);
    GrafoVial.Coordenadas c = grafoReal.coordenadas(nodo);
    assertThat(c.lat()).isBetween(-30.5, -29.5);
    assertThat(c.lon()).isBetween(-71.7, -70.5);
  }

  /**
   * IT-RN1: velocidades en el grafo real son todas positivas y en rango razonable (0, 200] km/h.
   */
  @Test
  @Tag("integration")
  void integracion_rn_velocidades_positivas_y_en_rango() throws IOException {
    GrafoVialJGraphT grafoReal = cargarGrafoReal();
    // Verificar sobre una muestra de nodos (primeros 100) para no tardar demasiado
    grafoReal.nodos().stream()
        .limit(100)
        .forEach(
            nodo -> {
              for (GrafoVial.Arista a : grafoReal.vecinos(nodo)) {
                assertThat(a.velocidadEfectivaKmh())
                    .as("velocidad de arista (%d->%d) debe ser positiva", a.origen(), a.destino())
                    .isGreaterThan(0.0)
                    .isLessThanOrEqualTo(200.0);
                assertThat(a.longitudM())
                    .as("longitud de arista (%d->%d) debe ser positiva", a.origen(), a.destino())
                    .isGreaterThan(0.0);
              }
            });
  }

  // --------------------------------------------------------------------------
  // Helper
  // --------------------------------------------------------------------------

  private static GrafoVialJGraphT cargarGrafoReal() throws IOException {
    // El GraphML real esta en data/graphs/coquimbo.graphml relativo a la raiz del monorepo
    // Desde core-java/, el path relativo es ../data/graphs/coquimbo.graphml
    Path graphml =
        Paths.get(System.getProperty("user.dir"))
            .resolve("../data/graphs/coquimbo.graphml")
            .normalize();
    return CargadorGrafo.cargarGrafoIvRegion(graphml);
  }
}
