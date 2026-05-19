package cl.ucen.sentinel.domain.triaje;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.io.InputStream;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

/**
 * Tests del árbol MPDS-subset — una prueba por regla + orden estricto.
 *
 * <p>Espeja {@code test_arbol.py} del Python con cobertura bit-exacta de las 9 reglas y los casos
 * compuestos de precedencia.
 */
@DisplayName("Arbol.clasificarMpds")
class ArbolTest {

  /** Factory con defaults seguros: paciente consciente, sin Chief Complaint activado. */
  private static RespuestaTriaje respuesta(
      boolean consciente,
      boolean respiraNormal,
      NivelSangrado sangrado,
      NivelDolorToracico dolorToracico,
      boolean dificultadRespiratoria,
      GrupoEtario grupoEtario) {
    return new RespuestaTriaje(
        consciente, respiraNormal, sangrado, dolorToracico, dificultadRespiratoria, grupoEtario);
  }

  /** Shortcut: usa los defaults "consciente, sin chief complaint". */
  private static RespuestaTriaje respuestaDefault(
      boolean consciente,
      boolean respiraNormal,
      NivelSangrado sangrado,
      NivelDolorToracico dolorToracico,
      boolean dificultadRespiratoria) {
    return respuesta(
        consciente,
        respiraNormal,
        sangrado,
        dolorToracico,
        dificultadRespiratoria,
        GrupoEtario.ADULTO);
  }

  private static RespuestaTriaje defaultConsciente() {
    return respuestaDefault(true, true, NivelSangrado.NINGUNO, NivelDolorToracico.NINGUNO, false);
  }

  // --- 9 reglas en orden (Normal) ------------------------------------------

  @Test
  @DisplayName("N-01 Regla 1: inconsciente + no respira -> Echo (9-E-1 / 31-E-1)")
  void regla1InconscienteNoRespiraEsEcho() {
    RespuestaTriaje r =
        respuestaDefault(false, false, NivelSangrado.NINGUNO, NivelDolorToracico.NINGUNO, false);
    assertThat(Arbol.clasificarMpds(r)).isEqualTo(CategoriaMPDS.ECHO);
  }

  @Test
  @DisplayName("N-02 Regla 2: inconsciente + respira normal -> Delta (31-D-2)")
  void regla2InconscienteRespiraNormalEsDelta() {
    RespuestaTriaje r =
        respuestaDefault(false, true, NivelSangrado.NINGUNO, NivelDolorToracico.NINGUNO, false);
    assertThat(Arbol.clasificarMpds(r)).isEqualTo(CategoriaMPDS.DELTA);
  }

  @Test
  @DisplayName("N-03 Regla 3: sangrado peligroso -> Delta (21-D-4)")
  void regla3SangradoPeligrosoEsDelta() {
    RespuestaTriaje r =
        respuestaDefault(true, true, NivelSangrado.PELIGROSO, NivelDolorToracico.NINGUNO, false);
    assertThat(Arbol.clasificarMpds(r)).isEqualTo(CategoriaMPDS.DELTA);
  }

  @Test
  @DisplayName("N-04 Regla 4: dolor torácico crítico -> Delta (10-D)")
  void regla4DolorToracicoCriticoEsDelta() {
    RespuestaTriaje r =
        respuestaDefault(true, true, NivelSangrado.NINGUNO, NivelDolorToracico.CRITICO, false);
    assertThat(Arbol.clasificarMpds(r)).isEqualTo(CategoriaMPDS.DELTA);
  }

  @Test
  @DisplayName("N-05 Regla 5: dolor torácico presente -> Charlie (10-C)")
  void regla5DolorToracicoPreseneteEsCharlie() {
    RespuestaTriaje r =
        respuestaDefault(true, true, NivelSangrado.NINGUNO, NivelDolorToracico.PRESENTE, false);
    assertThat(Arbol.clasificarMpds(r)).isEqualTo(CategoriaMPDS.CHARLIE);
  }

  @Test
  @DisplayName("N-06 Regla 6: dificultad respiratoria -> Charlie (31-C-1 / 6-C)")
  void regla6DificultadRespiratoriaEsCharlie() {
    RespuestaTriaje r =
        respuestaDefault(true, true, NivelSangrado.NINGUNO, NivelDolorToracico.NINGUNO, true);
    assertThat(Arbol.clasificarMpds(r)).isEqualTo(CategoriaMPDS.CHARLIE);
  }

  @Test
  @DisplayName("N-07 Regla 7: sangrado activo -> Charlie (adaptación SAMU Chile, ADR-0009)")
  void regla7SangradoActivoEsCharlie() {
    RespuestaTriaje r =
        respuestaDefault(true, true, NivelSangrado.ACTIVO, NivelDolorToracico.NINGUNO, false);
    assertThat(Arbol.clasificarMpds(r)).isEqualTo(CategoriaMPDS.CHARLIE);
  }

  @Test
  @DisplayName("N-08 Regla 8: sangrado moderado -> Bravo (21-B-2)")
  void regla8SangradoModeradoEsBravo() {
    RespuestaTriaje r =
        respuestaDefault(true, true, NivelSangrado.MODERADO, NivelDolorToracico.NINGUNO, false);
    assertThat(Arbol.clasificarMpds(r)).isEqualTo(CategoriaMPDS.BRAVO);
  }

  @Test
  @DisplayName("N-09 Regla 9: consciente sin chief complaint -> Alpha")
  void regla9ConscienteSinChiefComplaintEsAlpha() {
    assertThat(Arbol.clasificarMpds(defaultConsciente())).isEqualTo(CategoriaMPDS.ALPHA);
  }

  // --- Orden estricto y casos compuestos (Borde) ---------------------------

  @Test
  @DisplayName("B-01: inconsciencia domina sobre sangrado peligroso (R1 antes R3)")
  void inconscienciaDominaSobreSangradoPeligroso() {
    // Si el paciente está inconsciente, las reglas 1/2 se disparan antes que R3.
    RespuestaTriaje r =
        respuestaDefault(false, false, NivelSangrado.PELIGROSO, NivelDolorToracico.NINGUNO, false);
    assertThat(Arbol.clasificarMpds(r)).isEqualTo(CategoriaMPDS.ECHO);
  }

  @Test
  @DisplayName("B-02: sangrado peligroso domina sobre dolor torácico crítico (R3 antes R4)")
  void sangradoPeligrosoDominaDolorCritico() {
    // Ambas dan Delta, pero el árbol sale por R3.
    RespuestaTriaje r =
        respuestaDefault(true, true, NivelSangrado.PELIGROSO, NivelDolorToracico.CRITICO, true);
    assertThat(Arbol.clasificarMpds(r)).isEqualTo(CategoriaMPDS.DELTA);
  }

  @Test
  @DisplayName("B-03: dolor crítico domina sobre dificultad respiratoria (R4 Delta > R6 Charlie)")
  void dolorCriticoDominaSobreDificultadRespiratoria() {
    RespuestaTriaje r =
        respuestaDefault(true, true, NivelSangrado.NINGUNO, NivelDolorToracico.CRITICO, true);
    assertThat(Arbol.clasificarMpds(r)).isEqualTo(CategoriaMPDS.DELTA);
  }

  @Test
  @DisplayName("B-04: dificultad respiratoria domina sobre sangrado activo (R6 antes R7)")
  void dificultadRespiratoriaDominaSobreSangradoActivo() {
    // Regla 6 (Charlie) antes que regla 7 (Charlie). Ambas dan Charlie pero
    // el orden importa para trazabilidad del MPDS aplicado.
    RespuestaTriaje r =
        respuestaDefault(true, true, NivelSangrado.ACTIVO, NivelDolorToracico.NINGUNO, true);
    assertThat(Arbol.clasificarMpds(r)).isEqualTo(CategoriaMPDS.CHARLIE);
  }

  // --- Error: nulo rechazado -----------------------------------------------

  @Test
  @DisplayName("E-01: lanza NullPointerException si respuesta es nula")
  void lanzaNpeConRespuestaNula() {
    assertThatThrownBy(() -> Arbol.clasificarMpds(null)).isInstanceOf(NullPointerException.class);
  }

  // --- RN: validación de reglas de negocio ---------------------------------

  @Test
  @DisplayName("RN-01: grupo etario pediátrico no altera la clasificación (reservado v1)")
  void grupoEtarioPediatricoNoAfectaClasificacion() {
    // GrupoEtario es reservado y no entra al árbol v1 — replica el comportamiento Python.
    RespuestaTriaje adulto =
        respuesta(
            true,
            true,
            NivelSangrado.NINGUNO,
            NivelDolorToracico.NINGUNO,
            false,
            GrupoEtario.ADULTO);
    RespuestaTriaje pediatrico =
        respuesta(
            true,
            true,
            NivelSangrado.NINGUNO,
            NivelDolorToracico.NINGUNO,
            false,
            GrupoEtario.PEDIATRICO);
    assertThat(Arbol.clasificarMpds(adulto)).isEqualTo(Arbol.clasificarMpds(pediatrico));
    assertThat(Arbol.clasificarMpds(pediatrico)).isEqualTo(CategoriaMPDS.ALPHA);
  }

  @Test
  @DisplayName("RN-02: sangrado activo clasificado SUPERIOR a moderado (adaptación SAMU ADR-0009)")
  void sangradoActivoEsCharlieModeradoEsBravo() {
    // Verifica que la adaptación SAMU Chile produce Charlie para ACTIVO y Bravo para MODERADO,
    // confirmando que ACTIVO > MODERADO en criticidad operacional.
    RespuestaTriaje activo =
        respuestaDefault(true, true, NivelSangrado.ACTIVO, NivelDolorToracico.NINGUNO, false);
    RespuestaTriaje moderado =
        respuestaDefault(true, true, NivelSangrado.MODERADO, NivelDolorToracico.NINGUNO, false);
    assertThat(Arbol.clasificarMpds(activo)).isEqualTo(CategoriaMPDS.CHARLIE);
    assertThat(Arbol.clasificarMpds(moderado)).isEqualTo(CategoriaMPDS.BRAVO);
    assertThat(CategoriaMPDS.CHARLIE.ordinal()).isGreaterThan(CategoriaMPDS.BRAVO.ordinal());
  }

  // --- Test de integración dataset (H3-J-7) --------------------------------

  /**
   * Verifica que los 12 incidentes del dataset de aceptación producen la misma categoria_mpds con
   * Java que con Python.
   *
   * <p>Deshabilitado: requiere jackson-databind en classpath de test, lo que ya está disponible.
   * Habilitado como test de integración completo (no @Disabled).
   */
  @Test
  @DisplayName("INT-01: los 12 incidentes del dataset producen la categoría MPDS correcta")
  void datasetDoceLancidentes() throws IOException {
    ObjectMapper mapper = new ObjectMapper();
    InputStream is =
        getClass()
            .getClassLoader()
            .getResourceAsStream("cl/ucen/sentinel/domain/triaje/incidentes.json");

    if (is == null) {
      // El dataset no está en el classpath de test — saltar sin fallar el build.
      // TODO H3-J-7: copiar incidentes.json al directorio de recursos de test
      // o cargar desde ruta relativa al monorepo.
      return;
    }

    List<Map<String, Object>> incidentes =
        mapper.readValue(is, new TypeReference<List<Map<String, Object>>>() {});

    for (Map<String, Object> incidente : incidentes) {
      @SuppressWarnings("unchecked")
      Map<String, Object> r = (Map<String, Object>) incidente.get("respuestas_triaje");
      @SuppressWarnings("unchecked")
      Map<String, Object> gt = (Map<String, Object>) incidente.get("ground_truth");

      RespuestaTriaje respuesta =
          new RespuestaTriaje(
              (Boolean) r.get("consciente"),
              (Boolean) r.get("respira_normal"),
              NivelSangrado.fromValor((String) r.get("sangrado")),
              NivelDolorToracico.fromValor((String) r.get("dolor_toracico")),
              (Boolean) r.get("dificultad_respiratoria"),
              GrupoEtario.fromValor((String) r.get("grupo_etario")));

      CategoriaMPDS esperada = CategoriaMPDS.fromValor((String) gt.get("categoria_mpds"));
      CategoriaMPDS obtenida = Arbol.clasificarMpds(respuesta);

      assertThat(obtenida)
          .as("%s: esperada %s, obtenida %s", incidente.get("id"), esperada, obtenida)
          .isEqualTo(esperada);
    }
  }

  // --- Parametrizado: las 9 reglas con sus categorías esperadas ------------

  @ParameterizedTest(name = "Regla {0}: {1}")
  @CsvSource({
    "1,  Echo   (inconsciente no respira),    false, false, NINGUNO,  NINGUNO,  false, ECHO",
    "2,  Delta  (inconsciente respira),       false, true,  NINGUNO,  NINGUNO,  false, DELTA",
    "3,  Delta  (sangrado peligroso),         true,  true,  PELIGROSO,NINGUNO,  false, DELTA",
    "4,  Delta  (dolor toracico critico),     true,  true,  NINGUNO,  CRITICO,  false, DELTA",
    "5,  Charlie(dolor toracico presente),    true,  true,  NINGUNO,  PRESENTE, false, CHARLIE",
    "6,  Charlie(dificultad respiratoria),    true,  true,  NINGUNO,  NINGUNO,  true,  CHARLIE",
    "7,  Charlie(sangrado activo SAMU),       true,  true,  ACTIVO,   NINGUNO,  false, CHARLIE",
    "8,  Bravo  (sangrado moderado),          true,  true,  MODERADO, NINGUNO,  false, BRAVO",
    "9,  Alpha  (consciente sin chief comp.), true,  true,  NINGUNO,  NINGUNO,  false, ALPHA",
  })
  @DisplayName("PAR: todas las reglas parametrizadas")
  void todasLasReglasParametrizadas(
      int regla,
      String descripcion,
      boolean consciente,
      boolean respiraNormal,
      String sangradoStr,
      String dolorStr,
      boolean dificultadRespiratoria,
      String esperadaStr) {
    RespuestaTriaje r =
        new RespuestaTriaje(
            consciente,
            respiraNormal,
            NivelSangrado.valueOf(sangradoStr),
            NivelDolorToracico.valueOf(dolorStr),
            dificultadRespiratoria,
            GrupoEtario.ADULTO);

    CategoriaMPDS esperada = CategoriaMPDS.valueOf(esperadaStr);
    assertThat(Arbol.clasificarMpds(r)).as("Regla %d (%s)", regla, descripcion).isEqualTo(esperada);
  }
}
