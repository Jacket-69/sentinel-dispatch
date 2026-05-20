package cl.ucen.sentinel.cli;

import cl.ucen.sentinel.application.MotivoDespacho;
import cl.ucen.sentinel.application.ResultadoDespacho;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Serializa un {@link ResultadoDespacho} al schema JSONL congelado en ADR-0017.
 *
 * <p>Produce una línea JSON sin indentación, codificada en UTF-8, que cumple el contrato de
 * equivalencia para la validación dual Python-Java (ADR-0008, RT-02). El terminador de línea
 * ({@code \n}) es responsabilidad del llamador.
 *
 * <p>Orden de campos: igual que el serializador Python ({@code run_dataset_cmd.py}) para
 * legibilidad humana (el comparador {@code compare_outputs.py} parsea JSON y no depende del orden).
 *
 * <ul>
 *   <li>{@code incidente_id}: str
 *   <li>{@code categoria_mpds}: str (valor del enum, p.ej. "Alpha")
 *   <li>{@code unidad_seleccionada}: {@code {"id": str}} u {@code null} en saturación
 *   <li>{@code despacho_suboptimo}: bool literal
 *   <li>{@code motivo}: str en minúsculas ("optimo", "penalizado", "suboptimo_rn02", "saturacion")
 *   <li>{@code eta_segundos}: float o {@code null} en saturación
 *   <li>{@code costo}: objeto con {@code T_viaje}, {@code penalizacion}, {@code total} o {@code
 *       null} en saturación
 *   <li>{@code ruta}: array de strings (IDs de nodo OSM como str; vacío en saturación)
 * </ul>
 *
 * <p>Clase de utilidad final — no instanciar.
 */
public final class JsonlSerializer {

  private static final ObjectMapper MAPPER = new ObjectMapper();

  private JsonlSerializer() {
    throw new AssertionError("Clase de utilidad — no instanciar");
  }

  /**
   * Serializa un {@link ResultadoDespacho} a una cadena JSON de una sola línea.
   *
   * <p>El schema sigue el contrato ADR-0017:
   *
   * <ul>
   *   <li>Floats en notación decimal (no científica) para valores típicos 0..3600 s.
   *   <li>Los IDs de nodo de la ruta se serializan como strings para evitar drift de {@code int64}
   *       entre parsers (ADR-0017 §ruta).
   *   <li>{@code unidad_seleccionada} es {@code {"id": "..."}} o {@code null}.
   *   <li>{@code costo} es objeto con las tres claves o {@code null} en saturación.
   * </ul>
   *
   * @param resultado resultado del caso de uso de despacho
   * @return cadena JSON de una línea (sin terminador {@code \n})
   * @throws IllegalStateException si Jackson no puede serializar (no debería ocurrir con tipos
   *     estándar)
   */
  public static String serializar(ResultadoDespacho resultado) {
    Map<String, Object> doc = buildDoc(resultado);
    try {
      return MAPPER.writeValueAsString(doc);
    } catch (JsonProcessingException e) {
      throw new IllegalStateException("Error al serializar ResultadoDespacho a JSON", e);
    }
  }

  // ---------------------------------------------------------------------------
  // Helpers privados
  // ---------------------------------------------------------------------------

  /**
   * Construye el mapa ordenado con los campos del schema ADR-0017.
   *
   * @param resultado resultado del despacho a serializar
   * @return {@link LinkedHashMap} con el orden canónico de campos
   */
  private static Map<String, Object> buildDoc(ResultadoDespacho resultado) {
    boolean esSaturacion = resultado.motivo() == MotivoDespacho.SATURACION;

    // Orden de campos igual al Python para legibilidad humana
    Map<String, Object> doc = new LinkedHashMap<>();

    doc.put("incidente_id", resultado.incidente().id());
    doc.put("categoria_mpds", resultado.incidente().categoriaMpds().valor());

    // unidad_seleccionada: {"id": "..."} o null
    if (!esSaturacion && resultado.elegida() != null) {
      Map<String, String> unidadSel = new LinkedHashMap<>();
      unidadSel.put("id", resultado.elegida().id());
      doc.put("unidad_seleccionada", unidadSel);
    } else {
      doc.put("unidad_seleccionada", null);
    }

    doc.put("despacho_suboptimo", resultado.despachoSuboptimo());
    doc.put("motivo", resultado.motivo().valor());

    // eta_segundos: float o null
    if (!esSaturacion && resultado.costoElegida() != null) {
      double tViaje = resultado.costoElegida().tViajeS();
      doc.put("eta_segundos", Double.isFinite(tViaje) ? tViaje : null);
    } else {
      doc.put("eta_segundos", null);
    }

    // costo: objeto o null
    if (!esSaturacion && resultado.costoElegida() != null) {
      double tViaje = resultado.costoElegida().tViajeS();
      double pen = resultado.costoElegida().penalizacion();
      double total = resultado.costoElegida().valorTotalS();

      // Usar 0.0 cuando el valor es ∞ (fallback RN-02 con penalización infinita — raro pero seguro)
      double tViajeOut = Double.isFinite(tViaje) ? tViaje : 0.0;
      double penOut = Double.isFinite(pen) ? pen : 0.0;
      double totalOut = Double.isFinite(total) ? total : 0.0;

      Map<String, Double> costoObj = new LinkedHashMap<>();
      costoObj.put("T_viaje", tViajeOut);
      costoObj.put("penalizacion", penOut);
      costoObj.put("total", totalOut);
      doc.put("costo", costoObj);
    } else {
      doc.put("costo", null);
    }

    // ruta: array de strings (IDs de nodo OSM como String, no como long)
    List<String> rutaStr =
        resultado.rutaNodos().stream()
            .map(String::valueOf)
            .collect(java.util.stream.Collectors.toList());
    doc.put("ruta", rutaStr);

    return doc;
  }
}
