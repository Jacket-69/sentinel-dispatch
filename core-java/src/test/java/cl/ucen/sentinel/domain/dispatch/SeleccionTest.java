package cl.ucen.sentinel.domain.dispatch;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import cl.ucen.sentinel.domain.triaje.CategoriaMPDS;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

/**
 * Tests unitarios de {@link Seleccion#seleccionarUnidad}.
 *
 * <p>Espeja {@code test_seleccion.py} 1:1 (excluidos los 4 tests de {@code
 * TestHayCoberturaAlternativa} que no se portan — ver ADR-0008). Casos normativos cubiertos: CP-04,
 * CP-05, CP-11, RN-04.
 */
@DisplayName("Seleccion")
class SeleccionTest {

  // ---------------------------------------------------------------------------
  // Helpers de construcción (idénticos al Python)
  // ---------------------------------------------------------------------------

  private static Unidad u(String id, TipoUnidad tipo, EstadoUnidad estado) {
    return new Unidad(
        id, "AMB-" + id.substring(1), tipo, "Hospital test", -29.9077, -71.2535, estado);
  }

  private static Unidad u(String id, TipoUnidad tipo) {
    return u(id, tipo, EstadoUnidad.DISPONIBLE);
  }

  private static Incidente i(String id, CategoriaMPDS cat) {
    return new Incidente(id, -29.92, -71.26, cat, "2026-05-25T08:15:00-04:00");
  }

  // ---------------------------------------------------------------------------
  // Normal — camino feliz del argmin
  // ---------------------------------------------------------------------------

  @Nested
  @DisplayName("Normal")
  class Normal {

    @Test
    @DisplayName("N-01: una sola unidad disponible es la elegida")
    void unaSolaUnidadDisponibleEsLaElegida() {
      Unidad unidad = u("U01", TipoUnidad.AVANZADA);
      Incidente incidente = i("I-01", CategoriaMPDS.BRAVO);
      ResultadoSeleccion r =
          Seleccion.seleccionarUnidad(List.of(unidad), incidente, Map.of("U01", 120.0));
      assertThat(r.elegida()).isNotNull();
      assertThat(r.elegida().id()).isEqualTo("U01");
      assertThat(r.costoElegida()).isNotNull();
      assertThat(r.costoElegida().valorTotalS()).isEqualTo(120.0);
    }

    @Test
    @DisplayName("N-02: dos avanzadas — gana la más cercana")
    void dosAvanzadasGanaLaMasCercana() {
      Unidad u1 = u("U01", TipoUnidad.AVANZADA);
      Unidad u2 = u("U02", TipoUnidad.AVANZADA);
      Incidente incidente = i("I-04", CategoriaMPDS.CHARLIE);
      ResultadoSeleccion r =
          Seleccion.seleccionarUnidad(
              List.of(u1, u2), incidente, Map.of("U01", 200.0, "U02", 90.0));
      assertThat(r.elegida()).isNotNull();
      assertThat(r.elegida().id()).isEqualTo("U02");
    }

    @Test
    @DisplayName("N-03: candidatos ordenados ascendente por costo")
    void candidatosOrdenadosPorCostoAscendente() {
      Unidad u1 = u("U01", TipoUnidad.AVANZADA);
      Unidad u2 = u("U02", TipoUnidad.AVANZADA);
      Unidad u3 = u("U03", TipoUnidad.AVANZADA);
      Incidente incidente = i("I-04", CategoriaMPDS.CHARLIE);
      ResultadoSeleccion r =
          Seleccion.seleccionarUnidad(
              List.of(u3, u1, u2), incidente, Map.of("U01", 100.0, "U02", 200.0, "U03", 50.0));
      List<String> idsOrdenados = r.candidatos().stream().map(c -> c.unidad().id()).toList();
      assertThat(idsOrdenados).containsExactly("U03", "U01", "U02");
    }
  }

  // ---------------------------------------------------------------------------
  // Borde — flota vacía, única con costo ∞, sin tViaje provisto
  // ---------------------------------------------------------------------------

  @Nested
  @DisplayName("Borde")
  class Borde {

    @Test
    @DisplayName("B-01: flota vacía → elegida null, candidatos vacíos")
    void flotaVaciaDevuelveElegidaNull() {
      Incidente incidente = i("I-01", CategoriaMPDS.ALPHA);
      ResultadoSeleccion r = Seleccion.seleccionarUnidad(List.of(), incidente, Map.of());
      assertThat(r.elegida()).isNull();
      assertThat(r.costoElegida()).isNull();
      assertThat(r.candidatos()).isEmpty();
    }

    @Test
    @DisplayName("B-02: única Básica para Echo → elegida null, 1 candidato con costo infinito")
    void unicaBasicaParaEchoDevuelveElegidaNull() {
      Unidad u = u("U02", TipoUnidad.BASICA);
      Incidente incidente = i("I-10", CategoriaMPDS.ECHO);
      ResultadoSeleccion r =
          Seleccion.seleccionarUnidad(List.of(u), incidente, Map.of("U02", 60.0));
      assertThat(r.elegida()).isNull();
      assertThat(r.candidatos()).hasSize(1);
      assertThat(r.candidatos().get(0).costo().esInfinito()).isTrue();
    }

    @Test
    @DisplayName("B-03: unidad sin tViaje provisto se excluye silenciosamente")
    void unidadSinTViajeProvistoSeExcluye() {
      Unidad u1 = u("U01", TipoUnidad.AVANZADA);
      Unidad u2 = u("U02", TipoUnidad.AVANZADA);
      Incidente incidente = i("I-01", CategoriaMPDS.BRAVO);
      // Solo U01 tiene tViaje; U02 no → excluida silenciosamente.
      ResultadoSeleccion r =
          Seleccion.seleccionarUnidad(List.of(u1, u2), incidente, Map.of("U01", 100.0));
      assertThat(r.elegida()).isNotNull();
      assertThat(r.elegida().id()).isEqualTo("U01");
      assertThat(r.candidatos()).hasSize(1);
    }
  }

  // ---------------------------------------------------------------------------
  // Error — entradas inválidas que se propagan
  // ---------------------------------------------------------------------------

  @Nested
  @DisplayName("Error")
  class Error {

    @Test
    @DisplayName("E-01: tViaje negativo en el mapa propaga TViajeInvalidoException")
    void tViajeNegativoPropagaTViajeInvalidoException() {
      Unidad u = u("U01", TipoUnidad.AVANZADA);
      Incidente incidente = i("I-01", CategoriaMPDS.BRAVO);
      assertThatThrownBy(
              () -> Seleccion.seleccionarUnidad(List.of(u), incidente, Map.of("U01", -10.0)))
          .isInstanceOf(TViajeInvalidoException.class)
          .hasMessageContaining("inválido");
    }

    @Test
    @DisplayName("E-02: tViaje NaN en el mapa propaga TViajeInvalidoException")
    void tViajeNanPropagaTViajeInvalidoException() {
      Unidad u = u("U01", TipoUnidad.AVANZADA);
      Incidente incidente = i("I-01", CategoriaMPDS.BRAVO);
      assertThatThrownBy(
              () -> Seleccion.seleccionarUnidad(List.of(u), incidente, Map.of("U01", Double.NaN)))
          .isInstanceOf(TViajeInvalidoException.class)
          .hasMessageContaining("inválido");
    }

    @Test
    @DisplayName("E-03: tViaje = ∞ resulta en costo infinito — elegida null, candidato presente")
    void tViajeInfinitoResultaEnCostoInfinito() {
      Unidad u = u("U01", TipoUnidad.AVANZADA);
      Incidente incidente = i("I-01", CategoriaMPDS.BRAVO);
      ResultadoSeleccion r =
          Seleccion.seleccionarUnidad(
              List.of(u), incidente, Map.of("U01", Double.POSITIVE_INFINITY));
      assertThat(r.elegida()).isNull();
      assertThat(r.candidatos().get(0).costo().esInfinito()).isTrue();
    }
  }

  // ---------------------------------------------------------------------------
  // Regla de Negocio — CP-04, CP-05, CP-11 + RN-04
  // ---------------------------------------------------------------------------

  @Nested
  @DisplayName("ReglaDeNegocio")
  class ReglaDeNegocio {

    @Test
    @DisplayName("CP-04: Charlie + Avanzada lejana gana a Básica cercana")
    void cp04CharlieAvanzadaLejanaGanaABasicaCercana() {
      // U02 (Básica) a 90 s → costo = 90 + 600 = 690 s.
      // U01 (Avanzada) a 180 s → costo = 180 + 0 = 180 s.
      Unidad uAvanzada = u("U01", TipoUnidad.AVANZADA);
      Unidad uBasica = u("U02", TipoUnidad.BASICA);
      Incidente incidente = i("I-04", CategoriaMPDS.CHARLIE);
      ResultadoSeleccion r =
          Seleccion.seleccionarUnidad(
              List.of(uBasica, uAvanzada), incidente, Map.of("U01", 180.0, "U02", 90.0));
      assertThat(r.elegida()).isNotNull();
      assertThat(r.elegida().id()).isEqualTo("U01");
      assertThat(r.costoElegida()).isNotNull();
      assertThat(r.costoElegida().valorTotalS()).isEqualTo(180.0);
    }

    @Test
    @DisplayName("CP-05: Echo + Básica excluida (∞); Avanzada lejana sí gana")
    void cp05EchoBasicaExcluidaAvanzadaLejanaGana() {
      Unidad uAvanzada = u("U01", TipoUnidad.AVANZADA);
      Unidad uBasica = u("U02", TipoUnidad.BASICA);
      Incidente incidente = i("I-10", CategoriaMPDS.ECHO);
      ResultadoSeleccion r =
          Seleccion.seleccionarUnidad(
              List.of(uBasica, uAvanzada), incidente, Map.of("U01", 350.0, "U02", 60.0));
      assertThat(r.elegida()).isNotNull();
      assertThat(r.elegida().id()).isEqualTo("U01");
      List<CandidatoDespacho> candidatosInfinitos =
          r.candidatos().stream().filter(c -> c.costo().esInfinito()).toList();
      assertThat(candidatosInfinitos).hasSize(1);
      assertThat(candidatosInfinitos.get(0).unidad().id()).isEqualTo("U02");
    }

    @Test
    @DisplayName("CP-11: empate de costo → desempate lexicográfico (U03 gana sobre U07)")
    void cp11EmpateDesempateLexicografico() {
      Unidad u3 = u("U03", TipoUnidad.AVANZADA);
      Unidad u7 = u("U07", TipoUnidad.AVANZADA);
      Incidente incidente = i("I-04", CategoriaMPDS.CHARLIE);
      // Mismo tViaje → mismo costo → desempate por ID lex.
      ResultadoSeleccion r =
          Seleccion.seleccionarUnidad(
              List.of(u7, u3), incidente, Map.of("U03", 120.0, "U07", 120.0));
      assertThat(r.elegida()).isNotNull();
      assertThat(r.elegida().id()).isEqualTo("U03");
      List<String> ids = r.candidatos().stream().map(c -> c.unidad().id()).toList();
      assertThat(ids).containsExactly("U03", "U07");
    }

    @Test
    @DisplayName("RN-04: unidad en Taller excluida silenciosamente — no aparece en candidatos")
    void rn04UnidadTallerExcluidaSilenciosamente() {
      Unidad uTaller = u("U01", TipoUnidad.AVANZADA, EstadoUnidad.TALLER);
      Unidad uLibre = u("U02", TipoUnidad.AVANZADA, EstadoUnidad.DISPONIBLE);
      Incidente incidente = i("I-01", CategoriaMPDS.BRAVO);
      ResultadoSeleccion r =
          Seleccion.seleccionarUnidad(
              List.of(uTaller, uLibre), incidente, Map.of("U01", 50.0, "U02", 200.0));
      assertThat(r.elegida()).isNotNull();
      assertThat(r.elegida().id()).isEqualTo("U02");
      assertThat(r.candidatos().stream().noneMatch(c -> c.unidad().id().equals("U01"))).isTrue();
    }
  }
}
