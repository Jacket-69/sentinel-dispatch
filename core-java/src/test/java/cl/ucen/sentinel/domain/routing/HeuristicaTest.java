package cl.ucen.sentinel.domain.routing;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.within;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

/**
 * Tests de {@link Heuristica}: haversineM y haversineSegundos.
 *
 * <p>Espejo de {@code test_heuristica.py} Python. Taxonomía: Normal, Borde, Error, RN.
 */
class HeuristicaTest {

  // Coordenadas de referencia en la IV Region
  private static final double LAT_LA_SERENA = -29.9027;
  private static final double LON_LA_SERENA = -71.2519;
  private static final double LAT_COQUIMBO = -29.9666;
  private static final double LON_COQUIMBO = -71.3418;

  // Distancia La Serena <-> Coquimbo calculada por Haversine Python (referencia)
  private static final double DIST_LS_CQ_M = 11_204.06;

  // ==========================================================================
  // Normal
  // ==========================================================================

  /**
   * N-1: La Serena-Coquimbo es aproximadamente 11.2 km; tolerancia 5% frente al valor Python.
   *
   * <p>Espejo de {@code test_haversine_m_la_serena_coquimbo_aprox_11km}.
   */
  @Test
  void normal_haversineM_laSerena_coquimbo_aprox11km() {
    double dist = Heuristica.haversineM(LAT_LA_SERENA, LON_LA_SERENA, LAT_COQUIMBO, LON_COQUIMBO);
    assertThat(dist).isCloseTo(DIST_LS_CQ_M, within(DIST_LS_CQ_M * 0.05));
  }

  /**
   * N-2: haversineSegundos == haversineM / V_MAX_MS por construccion.
   *
   * <p>Espejo de {@code test_haversine_segundos_igual_a_distancia_sobre_vmax}.
   */
  @Test
  void normal_haversineSegundos_igualA_distanciasobreVmax() {
    double distM = Heuristica.haversineM(LAT_LA_SERENA, LON_LA_SERENA, LAT_COQUIMBO, LON_COQUIMBO);
    double esperado = distM / Heuristica.V_MAX_MS;
    double resultado =
        Heuristica.haversineSegundos(LAT_LA_SERENA, LON_LA_SERENA, LAT_COQUIMBO, LON_COQUIMBO);
    assertThat(resultado).isCloseTo(esperado, within(1e-9));
  }

  // ==========================================================================
  // Borde
  // ==========================================================================

  /**
   * B-1: Distancia de un punto a si mismo es 0.0.
   *
   * <p>Espejo de {@code test_haversine_m_mismo_punto_es_cero}.
   */
  @Test
  void borde_haversineM_mismoPoint_esCero() {
    double dist = Heuristica.haversineM(LAT_LA_SERENA, LON_LA_SERENA, LAT_LA_SERENA, LON_LA_SERENA);
    assertThat(dist).isEqualTo(0.0);
  }

  /**
   * B-2: haversineM es simetrica: d(a,b) == d(b,a).
   *
   * <p>Espejo de {@code test_haversine_m_es_simetrica}.
   */
  @Test
  void borde_haversineM_esSimetrica() {
    double dAB = Heuristica.haversineM(LAT_LA_SERENA, LON_LA_SERENA, LAT_COQUIMBO, LON_COQUIMBO);
    double dBA = Heuristica.haversineM(LAT_COQUIMBO, LON_COQUIMBO, LAT_LA_SERENA, LON_LA_SERENA);
    assertThat(dAB).isCloseTo(dBA, within(1e-9));
  }

  // ==========================================================================
  // Error
  // ==========================================================================

  /** E-1: Radio terrestre es exactamente 6_371_000.0 m (paridad Python). */
  @Test
  void error_radioTierra_esCorrecto() {
    assertThat(Heuristica.RADIO_TIERRA_M).isEqualTo(6_371_000.0);
  }

  /** E-2: V_MAX_MS es exactamente V_MAX_KMH * 1000.0 / 3600.0 (paridad Python). */
  @Test
  void error_vMaxMs_esConsistente() {
    double esperado = Heuristica.V_MAX_KMH * 1000.0 / 3600.0;
    assertThat(Heuristica.V_MAX_MS).isEqualTo(esperado);
  }

  // ==========================================================================
  // Regla de negocio (RN)
  // ==========================================================================

  /**
   * RN-1: haversineSegundos para coordenadas concretas coincide con el valor Python.
   *
   * <p>Espejo de {@code test_haversine_segundos_valores_concretos} Python. Los valores esperados
   * son calculados exactamente por Python y usados como ground truth.
   */
  @ParameterizedTest
  @CsvSource({
    // mismo punto -> 0 s
    "-29.9027, -71.2519, -29.9027, -71.2519, 0.0",
    // La Serena <-> Coquimbo: DIST_LS_CQ_M / V_MAX_MS = 11204.06 / 50.0 = 224.0812
    "-29.9027, -71.2519, -29.9666, -71.3418, 224.0812"
  })
  void rn_haversineSegundos_valoresConcretos(
      double lat1, double lon1, double lat2, double lon2, double esperadoS) {
    double resultado = Heuristica.haversineSegundos(lat1, lon1, lat2, lon2);
    // tolerancia 1% para el valor no-cero; abs para el cero
    assertThat(resultado).isCloseTo(esperadoS, within(Math.max(esperadoS * 0.01, 1e-9)));
  }
}
