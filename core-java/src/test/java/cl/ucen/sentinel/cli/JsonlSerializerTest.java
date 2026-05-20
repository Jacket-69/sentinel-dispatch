package cl.ucen.sentinel.cli;

import static org.assertj.core.api.Assertions.assertThat;

import cl.ucen.sentinel.application.MotivoDespacho;
import cl.ucen.sentinel.application.ResultadoDespacho;
import cl.ucen.sentinel.domain.dispatch.CandidatoDespacho;
import cl.ucen.sentinel.domain.dispatch.CostoDespacho;
import cl.ucen.sentinel.domain.dispatch.EstadoUnidad;
import cl.ucen.sentinel.domain.dispatch.Incidente;
import cl.ucen.sentinel.domain.dispatch.TipoUnidad;
import cl.ucen.sentinel.domain.dispatch.Unidad;
import cl.ucen.sentinel.domain.triaje.CategoriaMPDS;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

/**
 * Tests unitarios del serializador JSONL {@link JsonlSerializer}.
 *
 * <p>Taxonomía:
 *
 * <ul>
 *   <li>Normal: despacho óptimo, despacho penalizado.
 *   <li>RN: fallback RN-02 (suboptimo), saturación.
 *   <li>Borde: ruta vacía, nodo con ID grande.
 * </ul>
 */
class JsonlSerializerTest {

  private static final ObjectMapper MAPPER = new ObjectMapper();

  // ---------------------------------------------------------------------------
  // Helpers de fixtures
  // ---------------------------------------------------------------------------

  private static final Incidente INC_ALPHA =
      new Incidente("I-01", -29.91, -71.256, CategoriaMPDS.ALPHA, "2026-05-25T08:15:00-04:00");

  private static final Incidente INC_ECHO =
      new Incidente("I-10", -29.907, -71.257, CategoriaMPDS.ECHO, "2026-05-25T17:38:00-04:00");

  private static final Unidad U_AVANZADA =
      new Unidad(
          "U01",
          "AMB-001",
          TipoUnidad.AVANZADA,
          "Hospital Test",
          -29.9077,
          -71.2535,
          EstadoUnidad.DISPONIBLE);

  private static final Unidad U_BASICA =
      new Unidad(
          "U02",
          "AMB-002",
          TipoUnidad.BASICA,
          "CESFAM Test",
          -29.9015,
          -71.2433,
          EstadoUnidad.DISPONIBLE);

  /** Parsea la salida de {@link JsonlSerializer#serializar} a un {@link Map}. */
  @SuppressWarnings("unchecked")
  private Map<String, Object> parse(String json) throws IOException {
    return MAPPER.readValue(json, new TypeReference<Map<String, Object>>() {});
  }

  // ---------------------------------------------------------------------------
  // Normal-1: despacho óptimo (Alpha + Avanzada, sin penalización)
  // ---------------------------------------------------------------------------

  @Test
  void normal1_despachoOptimoProduceSchemaCompleto() throws IOException {
    CostoDespacho costo = new CostoDespacho(187.42, 187.42, 0.0, false);
    ResultadoDespacho resultado =
        new ResultadoDespacho(
            INC_ALPHA,
            U_AVANZADA,
            costo,
            MotivoDespacho.OPTIMO,
            false,
            List.of(new CandidatoDespacho(U_AVANZADA, 187.42, costo)),
            null,
            List.of(311738976L, 418800124L));

    String json = JsonlSerializer.serializar(resultado);
    Map<String, Object> doc = parse(json);

    assertThat(doc.get("incidente_id")).isEqualTo("I-01");
    assertThat(doc.get("categoria_mpds")).isEqualTo("Alpha");
    assertThat(doc.get("despacho_suboptimo")).isEqualTo(false);
    assertThat(doc.get("motivo")).isEqualTo("optimo");
    assertThat(((Number) doc.get("eta_segundos")).doubleValue()).isEqualTo(187.42);
    assertThat(doc.get("unidad_seleccionada"))
        .isInstanceOf(Map.class)
        .extracting("id")
        .isEqualTo("U01");

    @SuppressWarnings("unchecked")
    Map<String, Object> costoDoc = (Map<String, Object>) doc.get("costo");
    assertThat(costoDoc).containsKeys("T_viaje", "penalizacion", "total");
    assertThat(((Number) costoDoc.get("T_viaje")).doubleValue()).isEqualTo(187.42);
    assertThat(((Number) costoDoc.get("penalizacion")).doubleValue()).isEqualTo(0.0);

    @SuppressWarnings("unchecked")
    List<String> ruta = (List<String>) doc.get("ruta");
    assertThat(ruta).containsExactly("311738976", "418800124");
  }

  // ---------------------------------------------------------------------------
  // Normal-2: despacho penalizado (Charlie + Básica)
  // ---------------------------------------------------------------------------

  @Test
  void normal2_despachoPenalizadoReflejaPenalizacion() throws IOException {
    Incidente incCharlie =
        new Incidente("I-04", -29.90, -71.248, CategoriaMPDS.CHARLIE, "2026-05-25T11:05:00-04:00");
    // penalización = 600 s para Charlie + Básica
    double pen = 600.0;
    double tViaje = 120.0;
    double total = tViaje + pen;
    CostoDespacho costo = new CostoDespacho(total, tViaje, pen, false);
    ResultadoDespacho resultado =
        new ResultadoDespacho(
            incCharlie,
            U_BASICA,
            costo,
            MotivoDespacho.PENALIZADO,
            false,
            List.of(new CandidatoDespacho(U_BASICA, tViaje, costo)),
            null,
            List.of(1L, 2L, 3L));

    String json = JsonlSerializer.serializar(resultado);
    Map<String, Object> doc = parse(json);

    assertThat(doc.get("motivo")).isEqualTo("penalizado");
    assertThat(doc.get("despacho_suboptimo")).isEqualTo(false);
    assertThat(((Number) doc.get("eta_segundos")).doubleValue()).isEqualTo(tViaje);

    @SuppressWarnings("unchecked")
    Map<String, Object> costoDoc = (Map<String, Object>) doc.get("costo");
    assertThat(((Number) costoDoc.get("penalizacion")).doubleValue()).isEqualTo(pen);
    assertThat(((Number) costoDoc.get("total")).doubleValue()).isEqualTo(total);
  }

  // ---------------------------------------------------------------------------
  // RN-1: saturación — unidad_seleccionada, eta y costo son null; ruta vacía
  // ---------------------------------------------------------------------------

  @Test
  void rn1_saturacionProduceNullsYRutaVacia() throws IOException {
    ResultadoDespacho resultado =
        new ResultadoDespacho(
            INC_ECHO, null, null, MotivoDespacho.SATURACION, false, List.of(), null, List.of());

    String json = JsonlSerializer.serializar(resultado);
    Map<String, Object> doc = parse(json);

    assertThat(doc.get("motivo")).isEqualTo("saturacion");
    assertThat(doc.get("unidad_seleccionada")).isNull();
    assertThat(doc.get("eta_segundos")).isNull();
    assertThat(doc.get("costo")).isNull();

    @SuppressWarnings("unchecked")
    List<String> ruta = (List<String>) doc.get("ruta");
    assertThat(ruta).isEmpty();
  }

  // ---------------------------------------------------------------------------
  // RN-2: fallback RN-02 — despacho_suboptimo=true, motivo=suboptimo_rn02
  // ---------------------------------------------------------------------------

  @Test
  void rn2_fallbackRn02SuboptimoTrueYMotivoCorrect() throws IOException {
    double tViaje = 200.0;
    CostoDespacho costo = new CostoDespacho(tViaje, tViaje, 0.0, false);
    ResultadoDespacho resultado =
        new ResultadoDespacho(
            INC_ECHO,
            U_BASICA,
            costo,
            MotivoDespacho.SUBOPTIMO_RN02,
            true,
            List.of(new CandidatoDespacho(U_BASICA, tViaje, costo)),
            null,
            List.of(10L, 20L));

    String json = JsonlSerializer.serializar(resultado);
    Map<String, Object> doc = parse(json);

    assertThat(doc.get("motivo")).isEqualTo("suboptimo_rn02");
    assertThat(doc.get("despacho_suboptimo")).isEqualTo(true);
    assertThat(doc.get("unidad_seleccionada"))
        .isInstanceOf(Map.class)
        .extracting("id")
        .isEqualTo("U02");
  }

  // ---------------------------------------------------------------------------
  // Borde-1: la ruta serializa los IDs de nodo como Strings (no Long)
  // ---------------------------------------------------------------------------

  @Test
  void borde1_rutaNodosSerializadaComoStrings() throws IOException {
    CostoDespacho costo = new CostoDespacho(77.16, 77.16, 0.0, false);
    // Usar IDs de nodo grandes (típicos en OSM)
    List<Long> nodos = List.of(311738976L, 1223748567L, 418800124L);
    ResultadoDespacho resultado =
        new ResultadoDespacho(
            INC_ALPHA,
            U_AVANZADA,
            costo,
            MotivoDespacho.OPTIMO,
            false,
            List.of(new CandidatoDespacho(U_AVANZADA, 77.16, costo)),
            null,
            nodos);

    String json = JsonlSerializer.serializar(resultado);
    Map<String, Object> doc = parse(json);

    @SuppressWarnings("unchecked")
    List<Object> ruta = (List<Object>) doc.get("ruta");
    assertThat(ruta).allSatisfy(n -> assertThat(n).isInstanceOf(String.class));
    assertThat(ruta).containsExactly("311738976", "1223748567", "418800124");
  }

  // ---------------------------------------------------------------------------
  // Borde-2: el JSON producido es una sola línea sin salto de línea
  // ---------------------------------------------------------------------------

  @Test
  void borde2_salidaEsUnaLinea() {
    CostoDespacho costo = new CostoDespacho(100.0, 100.0, 0.0, false);
    ResultadoDespacho resultado =
        new ResultadoDespacho(
            INC_ALPHA,
            U_AVANZADA,
            costo,
            MotivoDespacho.OPTIMO,
            false,
            List.of(new CandidatoDespacho(U_AVANZADA, 100.0, costo)),
            null,
            List.of(1L));

    String json = JsonlSerializer.serializar(resultado);
    assertThat(json).doesNotContain("\n");
  }
}
