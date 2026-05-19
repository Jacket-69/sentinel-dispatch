package cl.ucen.sentinel.domain.routing;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.within;

import cl.ucen.sentinel.adapters.grafo.CargadorGrafo;
import java.io.IOException;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

/**
 * Tests del algoritmo A* — {@link AEstrella}.
 *
 * <p>Dos niveles: (a) tests unitarios con {@link FakeGrafoVial} sintético (rápidos, sin GraphML);
 * (b) tests de paridad bit-exacta con Python (cargan coquimbo.graphml real, marcados
 * {@code @Tag("integration")}).
 *
 * <p>Taxonomía: Normal, Borde, Error, RN.
 */
class AEstrellaTest {

  // ==========================================================================
  // Grafo sintético de 5 nodos (espejo del conftest.py Python)
  //
  // Topología (dirigida):
  //   0 --500m/50kmh-- 1 --700m/50kmh-- 2
  //   |                     \
  //   1000m/30kmh       100m/30kmh
  //   |                       \
  //   3 --300m/50kmh-- 4 --300m/50kmh-- 2
  //
  // Rutas posibles 0->2:
  //   Directa:    0->1->2 (500+700=1200m, 50kmh) => ETA 86.4 s
  //   Con atajo:  0->1->4->2 (500+100+300m, mix) => ETA 69.6 s  <-- optima
  //   Larga:      0->3->4->2 (1000+300+300m, mix) => lenta
  // ==========================================================================

  private static FakeGrafoVial grafoSimple5Nodos;

  @BeforeAll
  static void construirGrafoSimple() {
    grafoSimple5Nodos = new FakeGrafoVial();
    grafoSimple5Nodos.agregarNodo(0L, -29.9027, -71.2519); // centro La Serena
    grafoSimple5Nodos.agregarNodo(1L, -29.9027, -71.2474); // ~400 m al este
    grafoSimple5Nodos.agregarNodo(2L, -29.9027, -71.2412); // ~950 m al este
    grafoSimple5Nodos.agregarNodo(3L, -29.9117, -71.2519); // ~1000 m al sur
    grafoSimple5Nodos.agregarNodo(4L, -29.9117, -71.2474); // ~400 m este del nodo 3

    grafoSimple5Nodos.agregarArista(0L, 1L, 500.0, 50.0);
    grafoSimple5Nodos.agregarArista(1L, 2L, 700.0, 50.0);
    grafoSimple5Nodos.agregarArista(0L, 3L, 1000.0, 30.0);
    grafoSimple5Nodos.agregarArista(3L, 4L, 300.0, 50.0);
    grafoSimple5Nodos.agregarArista(4L, 2L, 300.0, 50.0);
    grafoSimple5Nodos.agregarArista(1L, 4L, 100.0, 30.0);
  }

  // ==========================================================================
  // Normal
  // ==========================================================================

  /**
   * N-1: El A* encuentra la ruta de menor ETA entre dos nodos conectados.
   *
   * <p>Ruta optima 0->2: 0->1->4->2 (69.6 s) es mas rapida que 0->1->2 (86.4 s). Espejo de {@code
   * test_camino_directo_es_optimo} Python.
   */
  @Test
  void normal_caminoDirecto_esOptimo() {
    AEstrella.Resultado r = AEstrella.aEstrella(grafoSimple5Nodos, 0L, 2L, 1.0, 1.0);
    assertThat(r.etaSegundos()).isCloseTo(69.6, within(0.001));
    assertThat(r.rutaNodos()).containsExactly(0L, 1L, 4L, 2L);
  }

  /**
   * N-2: El A* prefiere el desvio 0->1->4->2 sobre el camino lineal 0->1->2.
   *
   * <p>Espejo de {@code test_camino_con_desvio_mas_corto_es_preferido} Python.
   */
  @Test
  void normal_desvio_esMasRapidoQueLineal() {
    AEstrella.Resultado r = AEstrella.aEstrella(grafoSimple5Nodos, 0L, 2L, 1.0, 1.0);
    assertThat(r.rutaNodos())
        .as("A* no debe elegir la ruta mas lenta 0->1->2")
        .doesNotContainSequence(0L, 1L, 2L);
    assertThat(r.rutaNodos().get(0)).isEqualTo(0L);
    assertThat(r.rutaNodos().get(r.rutaNodos().size() - 1)).isEqualTo(2L);
  }

  // ==========================================================================
  // Borde
  // ==========================================================================

  /**
   * B-1: origen == destino retorna (0.0, [origen]) sin expandir el grafo.
   *
   * <p>Espejo de {@code test_origen_igual_destino_retorna_cero_y_lista_unitaria} Python.
   */
  @Test
  void borde_origenIgualDestino_retornaCeroYListaUnitaria() {
    AEstrella.Resultado r = AEstrella.aEstrella(grafoSimple5Nodos, 3L, 3L, 1.0, 1.0);
    assertThat(r.etaSegundos()).isEqualTo(0.0);
    assertThat(r.rutaNodos()).containsExactly(3L);
  }

  /**
   * B-2: Dos llamadas con los mismos argumentos retornan exactamente la misma ruta (determinismo).
   *
   * <p>Espejo de {@code test_tie_breaking_es_deterministico} Python.
   */
  @Test
  void borde_tibreBreaking_esDeterministico() {
    AEstrella.Resultado r1 = AEstrella.aEstrella(grafoSimple5Nodos, 0L, 2L, 1.0, 1.0);
    AEstrella.Resultado r2 = AEstrella.aEstrella(grafoSimple5Nodos, 0L, 2L, 1.0, 1.0);
    assertThat(r1.etaSegundos()).isEqualTo(r2.etaSegundos());
    assertThat(r1.rutaNodos()).isEqualTo(r2.rutaNodos());
  }

  // ==========================================================================
  // Error
  // ==========================================================================

  /**
   * E-1: Si el destino esta en un componente aislado, se lanza NoRutaDisponibleException.
   *
   * <p>Espejo de {@code test_sin_camino_lanza_no_ruta_disponible_error} Python.
   */
  @Test
  void error_sinCamino_lanzaNoRutaDisponibleException() {
    FakeGrafoVial g = new FakeGrafoVial();
    g.agregarNodo(0L, -29.9027, -71.2519);
    g.agregarNodo(1L, -29.9100, -71.2519);
    g.agregarNodo(99L, -29.8000, -71.2000); // nodo aislado sin aristas entrantes
    g.agregarArista(0L, 1L, 800.0, 50.0);

    assertThatThrownBy(() -> AEstrella.aEstrella(g, 0L, 99L, 1.0, 1.0))
        .isInstanceOf(NoRutaDisponibleException.class);
  }

  /**
   * E-2: factorHora &lt;= 0 lanza IllegalArgumentException.
   *
   * <p>Espejo de {@code test_factor_hora_invalido_lanza_value_error} Python.
   */
  @Test
  void error_factorHoraInvalido_lanzaIllegalArgumentException() {
    assertThatThrownBy(() -> AEstrella.aEstrella(grafoSimple5Nodos, 0L, 2L, 0.0, 1.0))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("factorHora");

    assertThatThrownBy(() -> AEstrella.aEstrella(grafoSimple5Nodos, 0L, 2L, -1.0, 1.0))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("factorHora");
  }

  // ==========================================================================
  // Regla de negocio (RN)
  // ==========================================================================

  /**
   * RN-1: factorSirena=1.5 reduce el ETA en factor 1.5 comparado con factorSirena=1.0.
   *
   * <p>Grafo lineal 0->1 (sin alternativa) garantiza que A* toma siempre la misma ruta. Espejo de
   * {@code test_factor_sirena_14_reduce_eta} Python, adaptado a factor 1.5 segun SRS.
   *
   * <p>Ground truth Python (2026-05-19): eta_base=513.606976, eta_sirena=342.404651, ratio=1.5.
   */
  @Test
  void rn_factorSirena15_reduceEta_enFactor15() {
    // Grafo lineal sin alternativa para aislamiento del efecto sirena
    FakeGrafoVial g = new FakeGrafoVial();
    g.agregarNodo(0L, -29.9027, -71.2519);
    g.agregarNodo(1L, -29.9027, -71.2412);
    g.agregarArista(0L, 1L, 1000.0, 50.0);

    AEstrella.Resultado etaBase = AEstrella.aEstrella(g, 0L, 1L, 1.0, 1.0);
    AEstrella.Resultado etaSirena = AEstrella.aEstrella(g, 0L, 1L, 1.0, 1.5);

    // sirena=1.5 hace la velocidad efectiva 1.5x mayor -> ETA 1.5x menor
    assertThat(etaSirena.etaSegundos())
        .isCloseTo(etaBase.etaSegundos() / 1.5, within(etaBase.etaSegundos() * 0.001));
  }

  // ==========================================================================
  // Integration: paridad bit-exacta con Python (cargan coquimbo.graphml real)
  // ==========================================================================

  /**
   * IT-N1 (paridad): par 1 — origen=297116528, destino=991537423.
   *
   * <p>Ground truth Python (2026-05-19): eta=67.891837 s, len_ruta=11.
   */
  @Test
  @Tag("integration")
  void integracion_paridad_par1_eta_y_lonRuta() throws IOException {
    GrafoVial grafo = cargarGrafoReal();
    AEstrella.Resultado r = AEstrella.aEstrella(grafo, 297116528L, 991537423L, 1.0, 1.0);
    assertThat(r.etaSegundos()).isCloseTo(67.891837, within(0.01));
    assertThat(r.rutaNodos()).hasSize(11).first().isEqualTo(297116528L);
    assertThat(r.rutaNodos().get(r.rutaNodos().size() - 1)).isEqualTo(991537423L);
  }

  /**
   * IT-N2 (paridad): par 2 — origen=989535066, destino=1914652967.
   *
   * <p>Ground truth Python (2026-05-19): eta=154.211895 s, len_ruta=19.
   */
  @Test
  @Tag("integration")
  void integracion_paridad_par2_eta_y_lonRuta() throws IOException {
    GrafoVial grafo = cargarGrafoReal();
    AEstrella.Resultado r = AEstrella.aEstrella(grafo, 989535066L, 1914652967L, 1.0, 1.0);
    assertThat(r.etaSegundos()).isCloseTo(154.211895, within(0.01));
    assertThat(r.rutaNodos()).hasSize(19).first().isEqualTo(989535066L);
    assertThat(r.rutaNodos().get(r.rutaNodos().size() - 1)).isEqualTo(1914652967L);
  }

  /**
   * IT-N3 (paridad): par 3 — origen=1001295419, destino=297116528 (Coquimbo->La Serena).
   *
   * <p>Ground truth Python (2026-05-19): eta=704.469478 s, len_ruta=70.
   */
  @Test
  @Tag("integration")
  void integracion_paridad_par3_coquimbo_laSerena() throws IOException {
    GrafoVial grafo = cargarGrafoReal();
    AEstrella.Resultado r = AEstrella.aEstrella(grafo, 1001295419L, 297116528L, 1.0, 1.0);
    assertThat(r.etaSegundos()).isCloseTo(704.469478, within(0.01));
    assertThat(r.rutaNodos()).hasSize(70).first().isEqualTo(1001295419L);
    assertThat(r.rutaNodos().get(r.rutaNodos().size() - 1)).isEqualTo(297116528L);
  }

  /**
   * IT-N4 (paridad): par 4 — origen=297117252 (Hospital San Juan), destino=1054581612 (Tierras
   * Blancas).
   *
   * <p>Ground truth Python (2026-05-19): eta=513.606976 s, len_ruta=38.
   */
  @Test
  @Tag("integration")
  void integracion_paridad_par4_hospitalSanJuan_tierrasBlancas() throws IOException {
    GrafoVial grafo = cargarGrafoReal();
    AEstrella.Resultado r = AEstrella.aEstrella(grafo, 297117252L, 1054581612L, 1.0, 1.0);
    assertThat(r.etaSegundos()).isCloseTo(513.606976, within(0.01));
    assertThat(r.rutaNodos()).hasSize(38).first().isEqualTo(297117252L);
    assertThat(r.rutaNodos().get(r.rutaNodos().size() - 1)).isEqualTo(1054581612L);
  }

  /**
   * IT-N5 (paridad): par 5 — origen=7389926280 (Las Companias), destino=1064753516 (Hospital San
   * Pablo Coquimbo).
   *
   * <p>Ground truth Python (2026-05-19): eta=861.029720 s, len_ruta=68.
   */
  @Test
  @Tag("integration")
  void integracion_paridad_par5_lasCompanias_hospitalSanPablo() throws IOException {
    GrafoVial grafo = cargarGrafoReal();
    AEstrella.Resultado r = AEstrella.aEstrella(grafo, 7389926280L, 1064753516L, 1.0, 1.0);
    assertThat(r.etaSegundos()).isCloseTo(861.029720, within(0.01));
    assertThat(r.rutaNodos()).hasSize(68).first().isEqualTo(7389926280L);
    assertThat(r.rutaNodos().get(r.rutaNodos().size() - 1)).isEqualTo(1064753516L);
  }

  /**
   * IT-RN1 (paridad + regla de negocio): factorSirena=1.5 reduce ETA en exactamente 1.5x.
   *
   * <p>Ground truth Python (2026-05-19): eta_base=513.606976, eta_sirena=342.404651, ratio=1.5.
   * Usamos el par 4 (Hospital San Juan -> Tierras Blancas) que tiene ruta unica optima estable.
   */
  @Test
  @Tag("integration")
  void integracion_rn_factorSirena15_reduceEta_paridad_python() throws IOException {
    GrafoVial grafo = cargarGrafoReal();
    AEstrella.Resultado base = AEstrella.aEstrella(grafo, 297117252L, 1054581612L, 1.0, 1.0);
    AEstrella.Resultado sirena = AEstrella.aEstrella(grafo, 297117252L, 1054581612L, 1.0, 1.5);

    assertThat(base.etaSegundos()).isCloseTo(513.606976, within(0.01));
    assertThat(sirena.etaSegundos()).isCloseTo(342.404651, within(0.01));
    // ratio exacto Python: 1.500000
    assertThat(base.etaSegundos() / sirena.etaSegundos()).isCloseTo(1.5, within(1e-4));
  }

  // --------------------------------------------------------------------------
  // Helper
  // --------------------------------------------------------------------------

  private static GrafoVial cargarGrafoReal() throws IOException {
    Path graphml =
        Paths.get(System.getProperty("user.dir"))
            .resolve("../data/graphs/coquimbo.graphml")
            .normalize();
    return CargadorGrafo.cargarGrafoIvRegion(graphml);
  }

  // ==========================================================================
  // FakeGrafoVial — implementacion in-memory de GrafoVial para tests unitarios
  // Espejo del GrafoFake Python en tests/unit/domain/routing/grafo_fake.py
  // ==========================================================================

  /**
   * Grafo dirigido in-memory para tests. Implementa {@link GrafoVial} sin dependencias externas.
   *
   * <p>Espejo de {@code GrafoFake} Python.
   */
  static final class FakeGrafoVial implements GrafoVial {

    private final java.util.Map<Long, Coordenadas> coords = new java.util.HashMap<>();
    private final java.util.Map<Long, List<Arista>> aristas = new java.util.HashMap<>();

    void agregarNodo(long nodo, double lat, double lon) {
      coords.put(nodo, new Coordenadas(lat, lon));
      aristas.putIfAbsent(nodo, new java.util.ArrayList<>());
    }

    void agregarArista(long origen, long destino, double longitudM, double velocidadKmh) {
      aristas
          .computeIfAbsent(origen, k -> new java.util.ArrayList<>())
          .add(new Arista(origen, destino, longitudM, velocidadKmh));
    }

    @Override
    public Coordenadas coordenadas(long nodo) {
      Coordenadas c = coords.get(nodo);
      if (c == null) {
        throw new IllegalArgumentException("Nodo no existe: " + nodo);
      }
      return c;
    }

    @Override
    public List<Arista> vecinos(long nodo) {
      List<Arista> lista = aristas.get(nodo);
      return lista != null ? java.util.Collections.unmodifiableList(lista) : List.of();
    }

    @Override
    public long nodoMasCercano(double lat, double lon) {
      return coords.entrySet().stream()
          .min(
              java.util.Comparator.comparingDouble(
                  e -> Heuristica.haversineM(lat, lon, e.getValue().lat(), e.getValue().lon())))
          .map(java.util.Map.Entry::getKey)
          .orElseThrow(() -> new IllegalStateException("Grafo vacio"));
    }

    @Override
    public java.util.Collection<Long> nodos() {
      return java.util.Collections.unmodifiableSet(coords.keySet());
    }
  }
}
