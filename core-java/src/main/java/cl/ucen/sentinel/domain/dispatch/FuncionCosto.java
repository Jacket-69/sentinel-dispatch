package cl.ucen.sentinel.domain.dispatch;

import cl.ucen.sentinel.domain.triaje.CategoriaMPDS;
import java.util.Map;

/**
 * Función de costo multiobjetivo del despacho (SRS sec. 2.6-C).
 *
 * <p>Implementa la fórmula normativa:
 *
 * <pre>
 *   Costo(u, i) = α · T_viaje(u → i) + β · Penalización_Idoneidad(u, i)
 * </pre>
 *
 * con {@code α = 1.0} (adimensional) y {@code β = 600 s} (escala la penalización categórica a
 * magnitud de desviación operativa equivalente a 10 minutos de viaje extra).
 *
 * <p>No conoce el routing: {@code tViajeS} se recibe ya calculado por el caller (application/
 * orquesta snap → A* → costo). Esa separación permite probar la función con valores sintéticos sin
 * grafo cargado (ADR-0014 §Decisión).
 *
 * <p>Clase de utilidad pura — no instanciar.
 *
 * <p>Fuente normativa: SRS sec. 2.6-C, tabla 2.6-C-1, RN-02, RN-04. Decisión arquitectónica:
 * ADR-0014.
 */
public final class FuncionCosto {

  private FuncionCosto() {
    throw new AssertionError("Clase de utilidad — no instanciar");
  }

  /**
   * Peso del tiempo de viaje en la función de costo (SRS sec. 2.6-C).
   *
   * <p>Adimensional. Mantenido en 1.0 mientras no haya evidencia empírica para recalibrarlo;
   * cualquier cambio requiere ADR explícito.
   */
  public static final double ALPHA = 1.0;

  /**
   * Peso de la penalización de idoneidad en segundos (SRS sec. 2.6-C).
   *
   * <p>Convierte el escalar de la tabla a magnitud temporal. {@code β = 600} significa que
   * penalización {@code 1} (Charlie + Básica) equivale a 10 minutos de viaje extra. Suficiente para
   * que una Avanzada lejana le gane a una Básica cercana en los rangos urbanos típicos de Coquimbo
   * (1-5 km).
   */
  public static final double BETA_S = 600.0;

  /**
   * Clave compuesta para la tabla de penalización (categoría MPDS × tipo de unidad).
   *
   * <p>Permite usar un {@code Map} inmutable con clave tipada en lugar de arrays o strings
   * concatenados.
   *
   * @param cat categoría MPDS
   * @param tipo tipo de unidad
   */
  record Clave(CategoriaMPDS cat, TipoUnidad tipo) {}

  /**
   * Penalización categórica por combinación MPDS × Tipo de Unidad.
   *
   * <p>Construida exhaustivamente (5 categorías × 2 tipos = 10 entradas) para que {@link
   * #penalizacionIdoneidad} no necesite branches condicionales y para que un revisor pueda
   * verificar la tabla al ojo contra el SRS sec. 2.6-C.
   *
   * <p>Reglas codificadas (SRS sec. 2.6-C tabla 1):
   *
   * <ul>
   *   <li>Echo + Avanzada / Delta + Avanzada: 0.0 (combinación ideal).
   *   <li>Echo + Básica / Delta + Básica: {@code ∞} (prohibida; RN-02 maneja el fallback).
   *   <li>Charlie + Avanzada: 0.0.
   *   <li>Charlie + Básica: 1.0 (penalizada pero no prohibida; β · 1 = 600 s de viaje extra).
   *   <li>Bravo / Alpha + Avanzada / Básica: 0.0 (cualquiera atiende).
   * </ul>
   */
  public static final Map<Clave, Double> TABLA_PENALIZACION_IDONEIDAD =
      Map.ofEntries(
          Map.entry(new Clave(CategoriaMPDS.ECHO, TipoUnidad.AVANZADA), 0.0),
          Map.entry(new Clave(CategoriaMPDS.ECHO, TipoUnidad.BASICA), Double.POSITIVE_INFINITY),
          Map.entry(new Clave(CategoriaMPDS.DELTA, TipoUnidad.AVANZADA), 0.0),
          Map.entry(new Clave(CategoriaMPDS.DELTA, TipoUnidad.BASICA), Double.POSITIVE_INFINITY),
          Map.entry(new Clave(CategoriaMPDS.CHARLIE, TipoUnidad.AVANZADA), 0.0),
          Map.entry(new Clave(CategoriaMPDS.CHARLIE, TipoUnidad.BASICA), 1.0),
          Map.entry(new Clave(CategoriaMPDS.BRAVO, TipoUnidad.AVANZADA), 0.0),
          Map.entry(new Clave(CategoriaMPDS.BRAVO, TipoUnidad.BASICA), 0.0),
          Map.entry(new Clave(CategoriaMPDS.ALPHA, TipoUnidad.AVANZADA), 0.0),
          Map.entry(new Clave(CategoriaMPDS.ALPHA, TipoUnidad.BASICA), 0.0));

  /**
   * Devuelve la penalización categórica para la combinación dada.
   *
   * <p>Consulta plana sobre {@link #TABLA_PENALIZACION_IDONEIDAD}. Si una combinación nueva se
   * agrega a los enums sin entrada en la tabla, el lookup falla con {@link IllegalStateException}
   * ruidoso — preferible a un default silencioso que podría enmascarar un bug del SRS.
   *
   * @param categoria salida del árbol de triaje (Alpha..Echo)
   * @param tipo tipo de unidad (Avanzada o Básica)
   * @return escalar finito (0.0 o 1.0) ó {@code Double.POSITIVE_INFINITY} para combinaciones
   *     prohibidas; antes de multiplicar por {@link #BETA_S}
   * @throws IllegalStateException si la combinación no está en la tabla (defensa anti-drift entre
   *     enums y tabla)
   */
  public static double penalizacionIdoneidad(CategoriaMPDS categoria, TipoUnidad tipo) {
    Double pen = TABLA_PENALIZACION_IDONEIDAD.get(new Clave(categoria, tipo));
    if (pen == null) {
      throw new IllegalStateException(
          "Combinación no registrada en tabla de penalización: " + categoria + " × " + tipo);
    }
    return pen;
  }

  /**
   * Calcula {@code Costo(u, i) = α · T_viaje + β · Penalización_Idoneidad}.
   *
   * <p>Orden de validaciones (igual que el Python):
   *
   * <ol>
   *   <li>Si la unidad está en {@link EstadoUnidad#TALLER} → lanza {@link
   *       UnidadInelegibleException} (RN-04). Este chequeo precede al de NaN (ver test {@code
   *       test_unidad_en_taller_error_previo_a_validacion_t_viaje}).
   *   <li>Si {@code tViajeS} es NaN o negativo → lanza {@link TViajeInvalidoException}.
   *   <li>Consulta la penalización en la tabla.
   *   <li>Si la penalización o el tViaje son infinitos → {@code CostoDespacho} con total infinito.
   *   <li>Si no → {@code α · tViajeS + β · penalización}.
   * </ol>
   *
   * @param unidad móvil SAMU candidato; {@link EstadoUnidad#TALLER} lanza excepción
   * @param incidente evento triado con categoría MPDS
   * @param tViajeS tiempo de viaje del A* en segundos; debe ser ≥ 0 y finito o {@code
   *     Double.POSITIVE_INFINITY}; NaN o negativo lanza {@link TViajeInvalidoException}
   * @return {@link CostoDespacho} con desglose; {@code esInfinito=true} cuando la penalización es
   *     infinita o cuando {@code tViajeS} es infinito
   * @throws UnidadInelegibleException si la unidad está en TALLER (RN-04)
   * @throws TViajeInvalidoException si {@code tViajeS} es NaN o negativo
   */
  public static CostoDespacho costo(Unidad unidad, Incidente incidente, double tViajeS) {
    // Validación 1: TALLER primero (RN-04). Debe preceder al chequeo de tViajeS
    // para que un llamador que pasa NaN con unidad en Taller reciba UnidadInelegibleException.
    if (unidad.estado() == EstadoUnidad.TALLER) {
      throw new UnidadInelegibleException(
          "Unidad " + unidad.id() + " está en Taller; RN-04 la excluye del cálculo.");
    }

    // Validación 2: tViajeS no puede ser NaN ni negativo.
    if (Double.isNaN(tViajeS) || tViajeS < 0.0) {
      throw new TViajeInvalidoException(
          "T_viaje="
              + tViajeS
              + " inválido para unidad "
              + unidad.id()
              + " → incidente "
              + incidente.id()
              + "; se espera valor finito ≥ 0 o math.inf.");
    }

    double pen = penalizacionIdoneidad(incidente.categoriaMpds(), unidad.tipo());

    // tViajeS infinito (sin ruta) o penalización infinita (combinación prohibida) → excluida.
    if (Double.isInfinite(pen) || Double.isInfinite(tViajeS)) {
      return new CostoDespacho(Double.POSITIVE_INFINITY, tViajeS, pen, true);
    }

    return new CostoDespacho(ALPHA * tViajeS + BETA_S * pen, tViajeS, pen, false);
  }
}
