package cl.ucen.sentinel.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.offset;

import cl.ucen.sentinel.domain.dispatch.EstadoUnidad;
import cl.ucen.sentinel.domain.dispatch.Incidente;
import cl.ucen.sentinel.domain.dispatch.TipoUnidad;
import cl.ucen.sentinel.domain.dispatch.Unidad;
import cl.ucen.sentinel.domain.routing.AEstrella;
import cl.ucen.sentinel.domain.routing.GrafoVial;
import cl.ucen.sentinel.domain.routing.NoRutaDisponibleException;
import cl.ucen.sentinel.domain.triaje.CategoriaMPDS;
import java.util.Collection;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

/**
 * Tests unitarios de {@link DespacharAmbulancia#despachar}.
 *
 * <p>Espeja {@code test_despacho.py} 1:1. La inyección de {@link CalculadorRuta} reemplaza el
 * {@code monkeypatch.setattr} del Python: cada test pasa una lambda que consulta un {@code Map}
 * parametrizable de tiempos por unidad.
 *
 * <p>Casos normativos cubiertos: CP-05, RN-02, RN-04, RN-08 / CP-10.
 */
@DisplayName("DespacharAmbulancia")
class DespacharAmbulanciaTest {

  // ---------------------------------------------------------------------------
  // Helpers de construcción — idénticos al Python
  // ---------------------------------------------------------------------------

  private static Unidad u(
      String id, TipoUnidad tipo, EstadoUnidad estado, double baseLat, double baseLon) {
    return new Unidad(
        id, "AMB-" + id.substring(1), tipo, "Hospital test", baseLat, baseLon, estado);
  }

  private static Unidad u(String id) {
    return u(id, TipoUnidad.AVANZADA, EstadoUnidad.DISPONIBLE, -29.9077, -71.2535);
  }

  private static Unidad u(String id, TipoUnidad tipo) {
    return u(id, tipo, EstadoUnidad.DISPONIBLE, -29.9077, -71.2535);
  }

  private static Unidad u(String id, TipoUnidad tipo, EstadoUnidad estado) {
    return u(id, tipo, estado, -29.9077, -71.2535);
  }

  private static Incidente inc(String id, CategoriaMPDS cat) {
    return new Incidente(id, -29.92, -71.26, cat, "2026-05-25T08:15:00-04:00");
  }

  // ---------------------------------------------------------------------------
  // Fake GrafoVial mínimo
  // ---------------------------------------------------------------------------

  /**
   * Grafo trivial que asigna nodo por índice según el orden de inserción de {@code nodosPorUnidad}.
   * El snap devuelve el nodo registrado para la unidad más cercana por coordenadas o el nodo del
   * incidente si coincide con las coords del incidente.
   */
  private static class FakeGrafo implements GrafoVial {

    private final Map<String, Long> nodosPorUnidadId; // unidad.id -> nodoBase
    private final Map<Long, GrafoVial.Coordenadas> coords = new HashMap<>();
    private final long nodoIncidente;

    FakeGrafo(Map<String, Long> nodosPorUnidadId, long nodoIncidente) {
      this.nodosPorUnidadId = nodosPorUnidadId;
      this.nodoIncidente = nodoIncidente;
      // nodo del incidente en coords fijas
      coords.put(nodoIncidente, new GrafoVial.Coordenadas(-29.92, -71.26));
    }

    /** Registra coordenadas sintéticas para nodos base. */
    void registrarCoords(long nodo, double lat, double lon) {
      coords.put(nodo, new GrafoVial.Coordenadas(lat, lon));
    }

    @Override
    public GrafoVial.Coordenadas coordenadas(long nodo) {
      GrafoVial.Coordenadas c = coords.get(nodo);
      if (c == null) {
        throw new IllegalArgumentException("Nodo desconocido en FakeGrafo: " + nodo);
      }
      return c;
    }

    @Override
    public List<GrafoVial.Arista> vecinos(long nodo) {
      if (nodo != nodoIncidente) {
        return List.of(new GrafoVial.Arista(nodo, nodoIncidente, 1000.0, 50.0));
      }
      return List.of();
    }

    @Override
    public long nodoMasCercano(double lat, double lon) {
      // Si coincide con coords del incidente → nodoIncidente
      if (Math.abs(lat - (-29.92)) < 0.01 && Math.abs(lon - (-71.26)) < 0.01) {
        return nodoIncidente;
      }
      // Buscar el nodo base con menor distancia euclídea
      long mejorNodo = nodoIncidente;
      double mejorDist = Double.MAX_VALUE;
      for (Map.Entry<Long, GrafoVial.Coordenadas> e : coords.entrySet()) {
        if (e.getKey() == nodoIncidente) continue;
        double dy = lat - e.getValue().lat();
        double dx = lon - e.getValue().lon();
        double d = dy * dy + dx * dx;
        if (d < mejorDist) {
          mejorDist = d;
          mejorNodo = e.getKey();
        }
      }
      return mejorNodo;
    }

    @Override
    public Collection<Long> nodos() {
      return coords.keySet();
    }

    /** Devuelve el nodo base registrado para la unidad indicada. */
    long nodoBase(String unidadId) {
      Long n = nodosPorUnidadId.get(unidadId);
      if (n == null) {
        throw new IllegalArgumentException("Unidad no registrada en FakeGrafo: " + unidadId);
      }
      return n;
    }
  }

  // ---------------------------------------------------------------------------
  // Factory de CalculadorRuta fake
  // ---------------------------------------------------------------------------

  /**
   * Crea un {@link CalculadorRuta} fake que resuelve el tiempo de la unidad cuyo nodo base coincide
   * con {@code origen}. Si el tiempo es infinito o no existe, lanza {@link
   * NoRutaDisponibleException}.
   *
   * @param tiempos mapa unidad.id → tViaje_s
   * @param grafo FakeGrafo para resolver origen → unidad.id
   * @return CalculadorRuta inyectable
   */
  private static CalculadorRuta fakeRouter(Map<String, Double> tiempos, FakeGrafo grafo) {
    // Construir el mapa inverso: nodoBase → unidadId
    Map<Long, String> nodoAUnidad = new HashMap<>();
    for (Map.Entry<String, Long> e : grafo.nodosPorUnidadId.entrySet()) {
      nodoAUnidad.put(e.getValue(), e.getKey());
    }
    return (g, origen, destino, fh, fs) -> {
      String uid = nodoAUnidad.get(origen);
      Double t = uid != null ? tiempos.get(uid) : null;
      if (t == null || Double.isInfinite(t)) {
        throw new NoRutaDisponibleException(origen, destino);
      }
      return new AEstrella.Resultado(t, List.of(origen, destino));
    };
  }

  // ---------------------------------------------------------------------------
  // Normal — camino feliz del orquestador
  // ---------------------------------------------------------------------------

  @Nested
  @DisplayName("Normal")
  class Normal {

    @Test
    @DisplayName("N-01: única Avanzada disponible para Bravo → OPTIMO, elegida=U01, tViaje=120")
    void unicaAvanzadaDisponibleParaBravoMotivoOptimo() {
      Map<String, Double> tiempos = Map.of("U01", 120.0);
      FakeGrafo grafo = new FakeGrafo(Map.of("U01", 1L), 99L);
      grafo.registrarCoords(1L, -29.9077, -71.2535);
      List<Unidad> flota = List.of(u("U01"));
      Incidente incidente = inc("I-01", CategoriaMPDS.BRAVO);

      ResultadoDespacho r =
          DespacharAmbulancia.despachar(
              incidente, flota, grafo, 1.0, 1.0, null, fakeRouter(tiempos, grafo));

      assertThat(r.motivo()).isSameAs(MotivoDespacho.OPTIMO);
      assertThat(r.elegida()).isNotNull();
      assertThat(r.elegida().id()).isEqualTo("U01");
      assertThat(r.costoElegida()).isNotNull();
      assertThat(r.costoElegida().tViajeS()).isCloseTo(120.0, offset(1e-9));
      assertThat(r.despachoSuboptimo()).isFalse();
    }

    @Test
    @DisplayName("N-02: dos Avanzadas → elegida la de menor tViaje")
    void dosAvanzadasGanaLaDeMenorTViaje() {
      Map<String, Double> tiempos = new HashMap<>();
      tiempos.put("U01", 300.0);
      tiempos.put("U02", 90.0);
      FakeGrafo grafo = new FakeGrafo(Map.of("U01", 1L, "U02", 2L), 99L);
      grafo.registrarCoords(1L, -29.9077, -71.2535);
      grafo.registrarCoords(2L, -29.9077, -71.2545);
      List<Unidad> flota =
          List.of(
              u("U01", TipoUnidad.AVANZADA, EstadoUnidad.DISPONIBLE, -29.9077, -71.2535),
              u("U02", TipoUnidad.AVANZADA, EstadoUnidad.DISPONIBLE, -29.9077, -71.2545));
      Incidente incidente = inc("I-02", CategoriaMPDS.BRAVO);

      ResultadoDespacho r =
          DespacharAmbulancia.despachar(
              incidente, flota, grafo, 1.0, 1.0, null, fakeRouter(tiempos, grafo));

      assertThat(r.motivo()).isSameAs(MotivoDespacho.OPTIMO);
      assertThat(r.elegida()).isNotNull();
      assertThat(r.elegida().id()).isEqualTo("U02");
      assertThat(r.despachoSuboptimo()).isFalse();
    }
  }

  // ---------------------------------------------------------------------------
  // Borde
  // ---------------------------------------------------------------------------

  @Nested
  @DisplayName("Borde")
  class Borde {

    @Test
    @DisplayName("B-01: Charlie con única Básica → PENALIZADO, penalización=1.0")
    void charlieConUnicaBasicaMotivoPenalizado() {
      Map<String, Double> tiempos = Map.of("U03", 200.0);
      FakeGrafo grafo = new FakeGrafo(Map.of("U03", 3L), 99L);
      grafo.registrarCoords(3L, -29.9077, -71.2535);
      List<Unidad> flota = List.of(u("U03", TipoUnidad.BASICA));
      Incidente incidente = inc("I-03", CategoriaMPDS.CHARLIE);

      ResultadoDespacho r =
          DespacharAmbulancia.despachar(
              incidente, flota, grafo, 1.0, 1.0, null, fakeRouter(tiempos, grafo));

      assertThat(r.motivo()).isSameAs(MotivoDespacho.PENALIZADO);
      assertThat(r.elegida()).isNotNull();
      assertThat(r.elegida().id()).isEqualTo("U03");
      assertThat(r.costoElegida()).isNotNull();
      assertThat(r.costoElegida().penalizacion()).isCloseTo(1.0, offset(1e-9));
      assertThat(r.despachoSuboptimo()).isFalse();
    }

    @Test
    @DisplayName("B-02: CP-05 Echo con Avanzada y Básica disponibles → OPTIMO, elegida=Avanzada")
    void echoConAvanzadaYBasicaDisponiblesEligeAvanzada() {
      Map<String, Double> tiempos = new HashMap<>();
      tiempos.put("U01", 150.0);
      tiempos.put("U04", 100.0); // Básica más cercana, pero inelegible para Echo
      FakeGrafo grafo = new FakeGrafo(Map.of("U01", 1L, "U04", 4L), 99L);
      grafo.registrarCoords(1L, -29.9077, -71.2535);
      grafo.registrarCoords(4L, -29.9077, -71.2545);
      List<Unidad> flota =
          List.of(
              u("U01", TipoUnidad.AVANZADA, EstadoUnidad.DISPONIBLE, -29.9077, -71.2535),
              u("U04", TipoUnidad.BASICA, EstadoUnidad.DISPONIBLE, -29.9077, -71.2545));
      Incidente incidente = inc("I-04", CategoriaMPDS.ECHO);

      ResultadoDespacho r =
          DespacharAmbulancia.despachar(
              incidente, flota, grafo, 1.0, 1.0, null, fakeRouter(tiempos, grafo));

      assertThat(r.motivo()).isSameAs(MotivoDespacho.OPTIMO);
      assertThat(r.elegida()).isNotNull();
      assertThat(r.elegida().id()).isEqualTo("U01");
      assertThat(r.costoElegida()).isNotNull();
      assertThat(r.costoElegida().esInfinito()).isFalse();
      assertThat(r.despachoSuboptimo()).isFalse();
    }

    @Test
    @DisplayName("B-03: flota completa en TALLER → SATURACION, elegida=null")
    void flotaCompletaEnTallerRetornaSaturacion() {
      FakeGrafo grafo = new FakeGrafo(Map.of("U05", 5L, "U06", 6L), 99L);
      grafo.registrarCoords(5L, -29.9077, -71.2535);
      grafo.registrarCoords(6L, -29.9077, -71.2545);
      List<Unidad> flota =
          List.of(
              u("U05", TipoUnidad.AVANZADA, EstadoUnidad.TALLER),
              u("U06", TipoUnidad.AVANZADA, EstadoUnidad.TALLER));
      Incidente incidente = inc("I-05", CategoriaMPDS.BRAVO);
      // Taller excluido por RN-04; no se necesita router porque no hay unidades que calcular
      Map<String, Double> tiempos = Map.of();

      ResultadoDespacho r =
          DespacharAmbulancia.despachar(
              incidente, flota, grafo, 1.0, 1.0, null, fakeRouter(tiempos, grafo));

      assertThat(r.motivo()).isSameAs(MotivoDespacho.SATURACION);
      assertThat(r.elegida()).isNull();
      assertThat(r.costoElegida()).isNull();
    }
  }

  // ---------------------------------------------------------------------------
  // Error — comportamiento frente a NoRutaDisponibleException
  // ---------------------------------------------------------------------------

  @Nested
  @DisplayName("Error")
  class Error {

    @Test
    @DisplayName("E-01: una unidad sin ruta (∞), otra con ruta → la con ruta gana, motivo=OPTIMO")
    void unaUnidadSinRutaOtraConRutaGanaLaConRuta() {
      Map<String, Double> tiempos = new HashMap<>();
      tiempos.put("U01", Double.POSITIVE_INFINITY); // fake lanzará NoRutaDisponibleException
      tiempos.put("U02", 180.0);
      FakeGrafo grafo = new FakeGrafo(Map.of("U01", 1L, "U02", 2L), 99L);
      grafo.registrarCoords(1L, -29.9077, -71.2535);
      grafo.registrarCoords(2L, -29.9077, -71.2545);
      List<Unidad> flota =
          List.of(
              u("U01", TipoUnidad.AVANZADA, EstadoUnidad.DISPONIBLE, -29.9077, -71.2535),
              u("U02", TipoUnidad.AVANZADA, EstadoUnidad.DISPONIBLE, -29.9077, -71.2545));
      Incidente incidente = inc("I-06", CategoriaMPDS.BRAVO);

      ResultadoDespacho r =
          DespacharAmbulancia.despachar(
              incidente, flota, grafo, 1.0, 1.0, null, fakeRouter(tiempos, grafo));

      assertThat(r.motivo()).isSameAs(MotivoDespacho.OPTIMO);
      assertThat(r.elegida()).isNotNull();
      assertThat(r.elegida().id()).isEqualTo("U02");
    }
  }

  // ---------------------------------------------------------------------------
  // Regla de Negocio
  // ---------------------------------------------------------------------------

  @Nested
  @DisplayName("Regla de Negocio")
  class ReglaDeNegocio {

    @Test
    @DisplayName(
        "RN-01: CP-05/RN-02 única Básica para Echo → SUBOPTIMO_RN02, esInfinito=true, tViaje=240")
    void rn02UnicaBasicaParaEcho() {
      Map<String, Double> tiempos = Map.of("U07", 240.0);
      FakeGrafo grafo = new FakeGrafo(Map.of("U07", 7L), 99L);
      grafo.registrarCoords(7L, -29.9077, -71.2535);
      List<Unidad> flota = List.of(u("U07", TipoUnidad.BASICA));
      Incidente incidente = inc("I-07", CategoriaMPDS.ECHO);

      ResultadoDespacho r =
          DespacharAmbulancia.despachar(
              incidente, flota, grafo, 1.0, 1.0, null, fakeRouter(tiempos, grafo));

      assertThat(r.motivo()).isSameAs(MotivoDespacho.SUBOPTIMO_RN02);
      assertThat(r.elegida()).isNotNull();
      assertThat(r.elegida().id()).isEqualTo("U07");
      assertThat(r.despachoSuboptimo()).isTrue();
      assertThat(r.costoElegida()).isNotNull();
      assertThat(r.costoElegida().esInfinito()).isTrue();
      assertThat(r.costoElegida().tViajeS()).isCloseTo(240.0, offset(1e-9));
    }

    @Test
    @DisplayName("RN-02: dos Básicas para Delta → SUBOPTIMO_RN02, gana la de menor tViaje")
    void rn02DosBasicasParaDeltaGanaMenorTViaje() {
      Map<String, Double> tiempos = new HashMap<>();
      tiempos.put("U02", 400.0);
      tiempos.put("U09", 150.0);
      FakeGrafo grafo = new FakeGrafo(Map.of("U02", 2L, "U09", 9L), 99L);
      grafo.registrarCoords(2L, -29.9077, -71.2535);
      grafo.registrarCoords(9L, -29.9077, -71.2545);
      List<Unidad> flota =
          List.of(
              u("U02", TipoUnidad.BASICA, EstadoUnidad.DISPONIBLE, -29.9077, -71.2535),
              u("U09", TipoUnidad.BASICA, EstadoUnidad.DISPONIBLE, -29.9077, -71.2545));
      Incidente incidente = inc("I-08", CategoriaMPDS.DELTA);

      ResultadoDespacho r =
          DespacharAmbulancia.despachar(
              incidente, flota, grafo, 1.0, 1.0, null, fakeRouter(tiempos, grafo));

      assertThat(r.motivo()).isSameAs(MotivoDespacho.SUBOPTIMO_RN02);
      assertThat(r.elegida()).isNotNull();
      assertThat(r.elegida().id()).isEqualTo("U09");
      assertThat(r.despachoSuboptimo()).isTrue();
    }

    @Test
    @DisplayName("RN-03: RN-02 empate tViaje → desempate lex (U02 sobre U07)")
    void rn02EmpateDesempateLexico() {
      Map<String, Double> tiempos = new HashMap<>();
      tiempos.put("U02", 300.0);
      tiempos.put("U07", 300.0);
      FakeGrafo grafo = new FakeGrafo(Map.of("U02", 2L, "U07", 7L), 99L);
      grafo.registrarCoords(2L, -29.9077, -71.2535);
      grafo.registrarCoords(7L, -29.9077, -71.2545);
      List<Unidad> flota =
          List.of(
              u("U07", TipoUnidad.BASICA, EstadoUnidad.DISPONIBLE, -29.9077, -71.2545),
              u("U02", TipoUnidad.BASICA, EstadoUnidad.DISPONIBLE, -29.9077, -71.2535));
      Incidente incidente = inc("I-09", CategoriaMPDS.ECHO);

      ResultadoDespacho r =
          DespacharAmbulancia.despachar(
              incidente, flota, grafo, 1.0, 1.0, null, fakeRouter(tiempos, grafo));

      assertThat(r.motivo()).isSameAs(MotivoDespacho.SUBOPTIMO_RN02);
      assertThat(r.elegida()).isNotNull();
      assertThat(r.elegida().id()).isEqualTo("U02");
      assertThat(r.despachoSuboptimo()).isTrue();
    }

    @Test
    @DisplayName(
        "RN-04: CP-10 dos EnRuta sin Disponibles → SATURACION + candidatas ordenadas por progreso")
    void cp10DosEnRutaSinDisponibles() {
      FakeGrafo grafo = new FakeGrafo(Map.of("U03", 3L, "U08", 8L), 99L);
      grafo.registrarCoords(3L, -29.9077, -71.2535);
      grafo.registrarCoords(8L, -29.9077, -71.2545);
      List<Unidad> flota =
          List.of(
              u("U03", TipoUnidad.AVANZADA, EstadoUnidad.EN_RUTA, -29.9077, -71.2535),
              u("U08", TipoUnidad.AVANZADA, EstadoUnidad.EN_RUTA, -29.9077, -71.2545));
      Incidente incidente = inc("I-10", CategoriaMPDS.BRAVO);
      Map<String, Double> progreso = Map.of("U03", 0.6, "U08", 0.3);
      // EN_RUTA no entran al argmin; se calcularán tiempos pero no son disponibles
      Map<String, Double> tiempos = new HashMap<>();
      tiempos.put("U03", 120.0);
      tiempos.put("U08", 90.0);

      ResultadoDespacho r =
          DespacharAmbulancia.despachar(
              incidente, flota, grafo, 1.0, 1.0, progreso, fakeRouter(tiempos, grafo));

      assertThat(r.motivo()).isSameAs(MotivoDespacho.SATURACION);
      assertThat(r.elegida()).isNull();
      assertThat(r.saturacion()).isNotNull();
      assertThat(r.saturacion().saturada()).isTrue();
      List<CandidataRedireccion> candidatas = r.saturacion().candidatasRedireccion();
      assertThat(candidatas).hasSize(2);
      // U08 primero (0.3 < 0.6)
      assertThat(candidatas.get(0).unidad().id()).isEqualTo("U08");
      assertThat(candidatas.get(0).progresoPct()).isCloseTo(0.3, offset(1e-9));
      assertThat(candidatas.get(1).unidad().id()).isEqualTo("U03");
      assertThat(candidatas.get(1).progresoPct()).isCloseTo(0.6, offset(1e-9));
    }

    @Test
    @DisplayName("RN-05: RN-04 Taller excluido; Avanzada disponible gana para Charlie")
    void rn04TallerExcluidoAvanzadaDisponibleGana() {
      Map<String, Double> tiempos = new HashMap<>();
      tiempos.put("U01", 200.0);
      tiempos.put("U10", 50.0); // Básica más cercana, pero Charlie+Básica pen=1.0
      FakeGrafo grafo = new FakeGrafo(Map.of("U01", 1L, "U05", 5L, "U10", 10L), 99L);
      grafo.registrarCoords(1L, -29.9077, -71.2535);
      grafo.registrarCoords(5L, -29.9077, -71.2545);
      grafo.registrarCoords(10L, -29.9077, -71.2555);
      List<Unidad> flota =
          List.of(
              u("U01", TipoUnidad.AVANZADA, EstadoUnidad.DISPONIBLE, -29.9077, -71.2535),
              u("U05", TipoUnidad.AVANZADA, EstadoUnidad.TALLER, -29.9077, -71.2545),
              u("U10", TipoUnidad.BASICA, EstadoUnidad.DISPONIBLE, -29.9077, -71.2555));
      Incidente incidente = inc("I-11", CategoriaMPDS.CHARLIE);

      ResultadoDespacho r =
          DespacharAmbulancia.despachar(
              incidente, flota, grafo, 1.0, 1.0, null, fakeRouter(tiempos, grafo));

      // U01: costo=200s; U10: costo=50+600=650s → U01 gana
      assertThat(r.motivo()).isSameAs(MotivoDespacho.OPTIMO);
      assertThat(r.elegida()).isNotNull();
      assertThat(r.elegida().id()).isEqualTo("U01");
      // U05 (Taller) no debe aparecer en candidatos
      List<String> candidatosIds = r.candidatos().stream().map(c -> c.unidad().id()).toList();
      assertThat(candidatosIds).doesNotContain("U05");
    }
  }

  // ---------------------------------------------------------------------------
  // Ruta de nodos
  // ---------------------------------------------------------------------------

  @Nested
  @DisplayName("Ruta de nodos")
  class RutaNodos {

    @Test
    @DisplayName(
        "N-01: despacho exitoso → rutaNodos.size()>=2, primero=nodoBase, último=nodoIncidente")
    void despachoExitosoRutaNodosPoblada() {
      long nodoBaseU01 = 1L;
      long nodoIncidente = 99L;
      Map<String, Double> tiempos = Map.of("U01", 120.0);
      FakeGrafo grafo = new FakeGrafo(Map.of("U01", nodoBaseU01), nodoIncidente);
      grafo.registrarCoords(nodoBaseU01, -29.9077, -71.2535);
      List<Unidad> flota = List.of(u("U01"));
      Incidente incidente = inc("I-rn-01", CategoriaMPDS.BRAVO);

      ResultadoDespacho r =
          DespacharAmbulancia.despachar(
              incidente, flota, grafo, 1.0, 1.0, null, fakeRouter(tiempos, grafo));

      assertThat(r.motivo()).isSameAs(MotivoDespacho.OPTIMO);
      assertThat(r.elegida()).isNotNull();
      assertThat(r.elegida().id()).isEqualTo("U01");
      assertThat(r.rutaNodos()).hasSizeGreaterThanOrEqualTo(2);
      assertThat(r.rutaNodos().get(0)).isEqualTo(nodoBaseU01);
      assertThat(r.rutaNodos().get(r.rutaNodos().size() - 1)).isEqualTo(nodoIncidente);
    }

    @Test
    @DisplayName("N-02: RN-02 fallback Básica para Echo → SUBOPTIMO_RN02, rutaNodos no vacía")
    void rn02FallbackBasicaRutaNodosPoblada() {
      long nodoBaseU07 = 7L;
      long nodoIncidente = 99L;
      Map<String, Double> tiempos = Map.of("U07", 240.0);
      FakeGrafo grafo = new FakeGrafo(Map.of("U07", nodoBaseU07), nodoIncidente);
      grafo.registrarCoords(nodoBaseU07, -29.9077, -71.2535);
      List<Unidad> flota = List.of(u("U07", TipoUnidad.BASICA));
      Incidente incidente = inc("I-rn-02", CategoriaMPDS.ECHO);

      ResultadoDespacho r =
          DespacharAmbulancia.despachar(
              incidente, flota, grafo, 1.0, 1.0, null, fakeRouter(tiempos, grafo));

      assertThat(r.motivo()).isSameAs(MotivoDespacho.SUBOPTIMO_RN02);
      assertThat(r.despachoSuboptimo()).isTrue();
      assertThat(r.elegida()).isNotNull();
      assertThat(r.elegida().id()).isEqualTo("U07");
      assertThat(r.rutaNodos()).isNotEmpty();
      assertThat(r.rutaNodos()).hasSizeGreaterThanOrEqualTo(2);
      assertThat(r.rutaNodos().get(0)).isEqualTo(nodoBaseU07);
      assertThat(r.rutaNodos().get(r.rutaNodos().size() - 1)).isEqualTo(nodoIncidente);
    }
  }
}
