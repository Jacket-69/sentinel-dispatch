package cl.ucen.sentinel.domain.dispatch;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.within;

import cl.ucen.sentinel.domain.triaje.CategoriaMPDS;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

/**
 * Tests unitarios de la función de costo multiobjetivo (SRS sec. 2.6-C).
 *
 * <p>Espeja {@code test_funcion_costo.py} 1:1. Casos normativos cubiertos: CP-04, CP-05, CP-11
 * (setup), RN-02, RN-04. Decisión arquitectónica de referencia: ADR-0014.
 */
@DisplayName("FuncionCosto")
class FuncionCostoTest {

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
  // PenalizacionIdoneidad
  // ---------------------------------------------------------------------------

  @Nested
  @DisplayName("PenalizacionIdoneidad")
  class PenalizacionIdoneidad {

    @ParameterizedTest(name = "{0} × {1} → {2}")
    @CsvSource({
      "ECHO, AVANZADA, 0.0",
      "DELTA, AVANZADA, 0.0",
      "CHARLIE, AVANZADA, 0.0",
      "BRAVO, AVANZADA, 0.0",
      "ALPHA, AVANZADA, 0.0",
      "BRAVO, BASICA, 0.0",
      "ALPHA, BASICA, 0.0",
      "CHARLIE, BASICA, 1.0"
    })
    @DisplayName("N-01: las 8 combinaciones con penalización finita devuelven el valor exacto")
    void penalizacionFinita(CategoriaMPDS categoria, TipoUnidad tipo, double esperado) {
      assertThat(FuncionCosto.penalizacionIdoneidad(categoria, tipo))
          .isCloseTo(esperado, within(1e-9));
    }

    @ParameterizedTest(name = "{0} × {1} → ∞ (combinación prohibida)")
    @CsvSource({"ECHO, BASICA", "DELTA, BASICA"})
    @DisplayName(
        "N-02: Echo/Delta + Básica devuelven infinito (combinación prohibida por idoneidad)")
    void penalizacionInfinita(CategoriaMPDS categoria, TipoUnidad tipo) {
      double resultado = FuncionCosto.penalizacionIdoneidad(categoria, tipo);
      assertThat(resultado).isInfinite();
    }

    @Test
    @DisplayName("N-03: la tabla cubre exhaustivamente 5 categorías × 2 tipos = 10 entradas")
    void tablaHasTenEntradas() {
      assertThat(FuncionCosto.TABLA_PENALIZACION_IDONEIDAD).hasSize(10);
    }

    @Test
    @DisplayName("N-04: ALPHA = 1.0 y BETA_S = 600.0 según SRS sec. 2.6-C")
    void constantesAlphaBetaConValoresNormativos() {
      assertThat(FuncionCosto.ALPHA).isCloseTo(1.0, within(1e-9));
      assertThat(FuncionCosto.BETA_S).isCloseTo(600.0, within(1e-9));
    }
  }

  // ---------------------------------------------------------------------------
  // CostoNormal
  // ---------------------------------------------------------------------------

  @Nested
  @DisplayName("CostoNormal")
  class CostoNormal {

    @Test
    @DisplayName("N-01: Charlie + Avanzada → penalización 0, costo total = T_viaje")
    void charlieAvanzadaCostoIgualATViaje() {
      CostoDespacho resultado =
          FuncionCosto.costo(
              u("U01", TipoUnidad.AVANZADA), i("I-01", CategoriaMPDS.CHARLIE), 300.0);
      assertThat(resultado.valorTotalS()).isCloseTo(300.0, within(1e-9));
      assertThat(resultado.penalizacion()).isCloseTo(0.0, within(1e-9));
      assertThat(resultado.esInfinito()).isFalse();
    }

    @Test
    @DisplayName("N-02: Bravo + Básica → penalización 0, costo total = T_viaje")
    void bravoBasicaCostoIgualATViaje() {
      CostoDespacho resultado =
          FuncionCosto.costo(u("U02", TipoUnidad.BASICA), i("I-02", CategoriaMPDS.BRAVO), 450.0);
      assertThat(resultado.valorTotalS()).isCloseTo(450.0, within(1e-9));
      assertThat(resultado.penalizacion()).isCloseTo(0.0, within(1e-9));
      assertThat(resultado.esInfinito()).isFalse();
    }

    @Test
    @DisplayName("N-03: Alpha + Básica → penalización 0, costo total = T_viaje")
    void alphaBasicaCostoIgualATViaje() {
      CostoDespacho resultado =
          FuncionCosto.costo(u("U03", TipoUnidad.BASICA), i("I-03", CategoriaMPDS.ALPHA), 120.0);
      assertThat(resultado.valorTotalS()).isCloseTo(120.0, within(1e-9));
      assertThat(resultado.penalizacion()).isCloseTo(0.0, within(1e-9));
      assertThat(resultado.esInfinito()).isFalse();
    }

    @Test
    @DisplayName("N-04: T_viaje = 0 con penalización 0 → costo = 0.0")
    void tViajeConCeroYPenalizacionCero() {
      CostoDespacho resultado =
          FuncionCosto.costo(u("U01", TipoUnidad.AVANZADA), i("I-04", CategoriaMPDS.BRAVO), 0.0);
      assertThat(resultado.valorTotalS()).isCloseTo(0.0, within(1e-9));
      assertThat(resultado.tViajeS()).isCloseTo(0.0, within(1e-9));
      assertThat(resultado.esInfinito()).isFalse();
    }

    @Test
    @DisplayName("N-05: Charlie + Básica → penalización 1.0, costo = T_viaje + 600")
    void charlieBasicaCostoTViajeMasBeta() {
      CostoDespacho resultado =
          FuncionCosto.costo(u("U02", TipoUnidad.BASICA), i("I-05", CategoriaMPDS.CHARLIE), 200.0);
      assertThat(resultado.valorTotalS())
          .isCloseTo(200.0 + FuncionCosto.BETA_S * 1.0, within(1e-9));
      assertThat(resultado.penalizacion()).isCloseTo(1.0, within(1e-9));
      assertThat(resultado.esInfinito()).isFalse();
    }

    @Test
    @DisplayName("N-06: costo() devuelve un record CostoDespacho inmutable")
    void resultadoEsCostoDespachoInmutable() {
      CostoDespacho resultado =
          FuncionCosto.costo(u("U01", TipoUnidad.AVANZADA), i("I-06", CategoriaMPDS.ALPHA), 60.0);
      assertThat(resultado).isInstanceOf(CostoDespacho.class);
    }
  }

  // ---------------------------------------------------------------------------
  // CostoBorde
  // ---------------------------------------------------------------------------

  @Nested
  @DisplayName("CostoBorde")
  class CostoBorde {

    @Test
    @DisplayName("B-01: T_viaje = ∞ (sin ruta A*) → esInfinito=true, total infinito")
    void tViajeInfinitoProduceEsInfinitoTrue() {
      CostoDespacho resultado =
          FuncionCosto.costo(
              u("U01", TipoUnidad.AVANZADA),
              i("I-07", CategoriaMPDS.CHARLIE),
              Double.POSITIVE_INFINITY);
      assertThat(resultado.esInfinito()).isTrue();
      assertThat(resultado.valorTotalS()).isInfinite();
    }

    @Test
    @DisplayName("B-02: T_viaje = 0 con penalización > 0 → costo = β · penalización")
    void tViajeCeroConPenalizacionPositiva() {
      CostoDespacho resultado =
          FuncionCosto.costo(u("U02", TipoUnidad.BASICA), i("I-08", CategoriaMPDS.CHARLIE), 0.0);
      assertThat(resultado.valorTotalS()).isCloseTo(FuncionCosto.BETA_S * 1.0, within(1e-9));
      assertThat(resultado.tViajeS()).isCloseTo(0.0, within(1e-9));
      assertThat(resultado.esInfinito()).isFalse();
    }

    @Test
    @DisplayName("B-03: T_viaje = 1e6 s (≈11.5 días) no genera overflow de float")
    void tViajeMuyGrandeNoOverflow() {
      CostoDespacho resultado =
          FuncionCosto.costo(u("U01", TipoUnidad.AVANZADA), i("I-09", CategoriaMPDS.DELTA), 1e6);
      assertThat(resultado.valorTotalS()).isCloseTo(1e6, within(1e-9));
      assertThat(Double.isFinite(resultado.valorTotalS())).isTrue();
    }

    @Test
    @DisplayName("B-04: unidad EN_RUTA (re-despacho RN-06) es elegible — no lanza excepción")
    void estadoEnRutaEsElegible() {
      CostoDespacho resultado =
          FuncionCosto.costo(
              u("U01", TipoUnidad.AVANZADA, EstadoUnidad.EN_RUTA),
              i("I-07", CategoriaMPDS.BRAVO),
              150.0);
      assertThat(resultado.valorTotalS()).isCloseTo(150.0, within(1e-9));
    }

    @Test
    @DisplayName("B-05: unidad EN_ESCENA es elegible para re-despacho — no lanza excepción")
    void estadoEnEscenaEsElegible() {
      CostoDespacho resultado =
          FuncionCosto.costo(
              u("U01", TipoUnidad.AVANZADA, EstadoUnidad.EN_ESCENA),
              i("I-08", CategoriaMPDS.ALPHA),
              75.0);
      assertThat(resultado.valorTotalS()).isCloseTo(75.0, within(1e-9));
    }

    @Test
    @DisplayName(
        "B-06: tViajeS se preserva en el record aunque penalización sea infinita (auditoría)")
    void tViajePreservadoCuandoPenalizacionInfinita() {
      CostoDespacho resultado =
          FuncionCosto.costo(u("U02", TipoUnidad.BASICA), i("I-10", CategoriaMPDS.ECHO), 60.0);
      assertThat(resultado.tViajeS()).isCloseTo(60.0, within(1e-9));
      assertThat(resultado.esInfinito()).isTrue();
    }
  }

  // ---------------------------------------------------------------------------
  // CostoError
  // ---------------------------------------------------------------------------

  @Nested
  @DisplayName("CostoError")
  class CostoError {

    @Test
    @DisplayName("E-01: NaN no es un tiempo de viaje físicamente válido → TViajeInvalidoException")
    void tViajeNanLanzaTViajeInvalidoException() {
      assertThatThrownBy(
              () ->
                  FuncionCosto.costo(
                      u("U01", TipoUnidad.AVANZADA), i("I-01", CategoriaMPDS.CHARLIE), Double.NaN))
          .isInstanceOf(TViajeInvalidoException.class)
          .hasMessageContaining("inválido");
    }

    @Test
    @DisplayName("E-02: T_viaje < 0 es físicamente imposible → TViajeInvalidoException")
    void tViajeNegativoLanzaTViajeInvalidoException() {
      assertThatThrownBy(
              () ->
                  FuncionCosto.costo(
                      u("U01", TipoUnidad.AVANZADA), i("I-01", CategoriaMPDS.BRAVO), -1.0))
          .isInstanceOf(TViajeInvalidoException.class)
          .hasMessageContaining("inválido");
    }

    @Test
    @DisplayName("E-03: T_viaje = -1e9 también lanza TViajeInvalidoException")
    void tViajeMuyNegativoLanzaTViajeInvalidoException() {
      assertThatThrownBy(
              () ->
                  FuncionCosto.costo(
                      u("U01", TipoUnidad.AVANZADA), i("I-01", CategoriaMPDS.ALPHA), -1e9))
          .isInstanceOf(TViajeInvalidoException.class)
          .hasMessageContaining("inválido");
    }

    @Test
    @DisplayName("E-04: RN-04 — unidad en TALLER lanza UnidadInelegibleException con 'RN-04'")
    void unidadEnTallerLanzaUnidadInelegibleException() {
      assertThatThrownBy(
              () ->
                  FuncionCosto.costo(
                      u("U05", TipoUnidad.AVANZADA, EstadoUnidad.TALLER),
                      i("I-02", CategoriaMPDS.BRAVO),
                      300.0))
          .isInstanceOf(UnidadInelegibleException.class)
          .hasMessageContaining("RN-04");
    }

    @Test
    @DisplayName("E-05: el mensaje de UnidadInelegibleException incluye el ID de la unidad")
    void unidadEnTallerErrorIncluyeIdUnidad() {
      assertThatThrownBy(
              () ->
                  FuncionCosto.costo(
                      u("U07", TipoUnidad.BASICA, EstadoUnidad.TALLER),
                      i("I-03", CategoriaMPDS.CHARLIE),
                      100.0))
          .isInstanceOf(UnidadInelegibleException.class)
          .hasMessageContaining("U07");
    }

    @Test
    @DisplayName("E-06: Taller lanza antes que NaN — orden de validaciones correcto")
    void unidadEnTallerErrorPrevioAValidacionTViaje() {
      // La guarda de Taller debe preceder al chequeo de NaN.
      assertThatThrownBy(
              () ->
                  FuncionCosto.costo(
                      u("U08", TipoUnidad.AVANZADA, EstadoUnidad.TALLER),
                      i("I-04", CategoriaMPDS.DELTA),
                      Double.NaN))
          .isInstanceOf(UnidadInelegibleException.class)
          .hasMessageContaining("RN-04");
    }
  }

  // ---------------------------------------------------------------------------
  // CostoReglaDeNegocio
  // ---------------------------------------------------------------------------

  @Nested
  @DisplayName("CostoReglaDeNegocio")
  class CostoReglaDeNegocio {

    @Test
    @DisplayName("RN-01 CP-04: Avanzada a 180 s gana a Básica a 90 s en incidente Charlie")
    void cp04AvanzadaLejanaganaABasicaCercanaCharlie() {
      // U01 (Avanzada, T=180 s) → costo = 1·180 + 600·0 = 180.0
      // U02 (Básica,   T=90 s)  → costo = 1·90  + 600·1 = 690.0
      Incidente i04 = i("I-04", CategoriaMPDS.CHARLIE);
      CostoDespacho costoU01 = FuncionCosto.costo(u("U01", TipoUnidad.AVANZADA), i04, 180.0);
      CostoDespacho costoU02 = FuncionCosto.costo(u("U02", TipoUnidad.BASICA), i04, 90.0);

      assertThat(costoU01.valorTotalS()).isCloseTo(180.0, within(1e-9));
      assertThat(costoU02.valorTotalS()).isCloseTo(690.0, within(1e-9));
      assertThat(costoU01.valorTotalS()).isLessThan(costoU02.valorTotalS());
    }

    @Test
    @DisplayName("RN-02 CP-05: Echo + Básica → valorTotalS = ∞, esInfinito = true")
    void cp05EchoBasicaProduceCostoInfinito() {
      CostoDespacho resultado =
          FuncionCosto.costo(u("U02", TipoUnidad.BASICA), i("I-10", CategoriaMPDS.ECHO), 60.0);
      assertThat(resultado.esInfinito()).isTrue();
      assertThat(resultado.valorTotalS()).isInfinite();
      assertThat(resultado.penalizacion()).isInfinite();
    }

    @Test
    @DisplayName("RN-02 CP-05 auditoría: tViajeS se preserva aunque el total sea infinito")
    void cp05TViajePreservadoEnCostoInfinito() {
      CostoDespacho resultado =
          FuncionCosto.costo(u("U02", TipoUnidad.BASICA), i("I-10", CategoriaMPDS.ECHO), 60.0);
      assertThat(resultado.tViajeS()).isCloseTo(60.0, within(1e-9));
    }

    @Test
    @DisplayName("RN-02: Delta + Básica también prohibida → costo infinito")
    void rn02DeltaBasicaProduceCostoInfinito() {
      CostoDespacho resultado =
          FuncionCosto.costo(u("U02", TipoUnidad.BASICA), i("I-11", CategoriaMPDS.DELTA), 45.0);
      assertThat(resultado.esInfinito()).isTrue();
      assertThat(resultado.valorTotalS()).isInfinite();
      assertThat(resultado.tViajeS()).isCloseTo(45.0, within(1e-9));
    }

    @Test
    @DisplayName("CP-11 setup: dos Avanzadas con mismo T_viaje → valorTotalS idéntico")
    void cp11SetupDosAvanzadasMismoTViajeCostoIgual() {
      Incidente inc = i("I-06", CategoriaMPDS.CHARLIE);
      CostoDespacho costoA = FuncionCosto.costo(u("U01", TipoUnidad.AVANZADA), inc, 200.0);
      CostoDespacho costoB = FuncionCosto.costo(u("U02", TipoUnidad.AVANZADA), inc, 200.0);
      assertThat(costoA.valorTotalS()).isCloseTo(costoB.valorTotalS(), within(1e-9));
    }

    @Test
    @DisplayName("RN-04: función de costo falla ruidoso ante unidad en Taller")
    void rn04TallerLanzaUnidadInelegibleException() {
      assertThatThrownBy(
              () ->
                  FuncionCosto.costo(
                      u("U09", TipoUnidad.AVANZADA, EstadoUnidad.TALLER),
                      i("I-07", CategoriaMPDS.BRAVO),
                      50.0))
          .isInstanceOf(UnidadInelegibleException.class)
          .hasMessageContaining("RN-04");
    }

    @Test
    @DisplayName("Determinismo: 100 llamadas idénticas devuelven siempre el mismo resultado")
    void determinismo100EjecucionesMismoInput() {
      Unidad unidad = u("U01", TipoUnidad.AVANZADA);
      Incidente incidente = i("I-05", CategoriaMPDS.CHARLIE);
      CostoDespacho referencia = FuncionCosto.costo(unidad, incidente, 300.0);
      for (int k = 0; k < 99; k++) {
        assertThat(FuncionCosto.costo(unidad, incidente, 300.0)).isEqualTo(referencia);
      }
    }

    @Test
    @DisplayName("Echo + Avanzada: combinación ideal → penalización 0, costo finito")
    void echoAvanzadaCostoFinito() {
      CostoDespacho resultado =
          FuncionCosto.costo(u("U01", TipoUnidad.AVANZADA), i("I-12", CategoriaMPDS.ECHO), 240.0);
      assertThat(resultado.valorTotalS()).isCloseTo(240.0, within(1e-9));
      assertThat(resultado.esInfinito()).isFalse();
      assertThat(resultado.penalizacion()).isCloseTo(0.0, within(1e-9));
    }
  }
}
