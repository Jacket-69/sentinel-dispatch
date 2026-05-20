package cl.ucen.sentinel.application;

import cl.ucen.sentinel.domain.dispatch.CandidatoDespacho;
import cl.ucen.sentinel.domain.dispatch.CostoDespacho;
import cl.ucen.sentinel.domain.dispatch.EstadoUnidad;
import cl.ucen.sentinel.domain.dispatch.FuncionCosto;
import cl.ucen.sentinel.domain.dispatch.Incidente;
import cl.ucen.sentinel.domain.dispatch.ResultadoSeleccion;
import cl.ucen.sentinel.domain.dispatch.Seleccion;
import cl.ucen.sentinel.domain.dispatch.TipoUnidad;
import cl.ucen.sentinel.domain.dispatch.Unidad;
import cl.ucen.sentinel.domain.routing.AEstrella;
import cl.ucen.sentinel.domain.routing.NoRutaDisponibleException;
import cl.ucen.sentinel.domain.triaje.CategoriaMPDS;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.logging.Logger;
import java.util.stream.StreamSupport;

/**
 * Orquestador de despacho de ambulancia (capa application).
 *
 * <p>Combina las piezas del dominio en un caso de uso end-to-end: dado un incidente triado y una
 * flota, calcula tiempos de viaje vía routing, ejecuta la selección óptima (función de costo +
 * argmin), aplica el fallback RN-02 cuando corresponde y reporta saturación cuando no hay unidades
 * elegibles.
 *
 * <p><b>Lo que SÍ vive acá</b> (capa application — política operativa):
 *
 * <ul>
 *   <li>Snap de origen (base de cada unidad) y destino (incidente) al grafo.
 *   <li>Cálculo de {@code T_viaje} por unidad vía {@link CalculadorRuta} (inyectable).
 *   <li>Filtrado por estado: solo unidades DISPONIBLE entran al argmin.
 *   <li>Política de fallback RN-02: si el argmin retorna {@code elegida=null} porque todas las
 *       Disponibles son Básicas para un incidente Echo/Delta, despachar igual con la Básica de
 *       menor {@code T_viaje} y marcar {@code despachoSuboptimo=true}.
 *   <li>Detección de saturación cuando no hay Disponibles (RN-08, vía {@link Saturacion#detectar}).
 * </ul>
 *
 * <p><b>Lo que NO vive acá</b> (dominio puro):
 *
 * <ul>
 *   <li>Fórmula del costo (vive en {@link FuncionCosto}).
 *   <li>Tabla de penalización de idoneidad (ídem).
 *   <li>Algoritmo A* (vive en {@link AEstrella}).
 *   <li>Validación de coordenadas IV Región (adapter de entrada).
 * </ul>
 *
 * <p>La separación está documentada en ADR-0014 y ADR-0015.
 *
 * <p>Clase de utilidad pura — no instanciar.
 *
 * <p>Fuente normativa: SRS sec. 2.5 (flujo principal), 2.6-C/D (costo y selección), 2.7 RN-02 /
 * RN-04 / RN-08, sec. 2.13 CP-04/05/10.
 */
public final class DespacharAmbulancia {

  private DespacharAmbulancia() {
    throw new AssertionError("Clase de utilidad — no instanciar");
  }

  private static final Logger LOG = Logger.getLogger(DespacharAmbulancia.class.getName());

  /**
   * Categorías MPDS sobre las que opera el fallback RN-02 (Echo y Delta).
   *
   * <p>Son las que la tabla de penalización marca como {@code ∞} para Básica. La diferencia con el
   * dominio: el dominio reporta {@code ∞}, la política RN-02 decide qué hacer con ese {@code ∞}
   * cuando no hay alternativa.
   */
  public static final Set<CategoriaMPDS> CATEGORIAS_CRITICAS_RN02 =
      Set.of(CategoriaMPDS.ECHO, CategoriaMPDS.DELTA);

  /**
   * Implementación de producción: method reference al A* puro (ADR-0015 §inyección).
   *
   * <p>Utilizada en la sobrecarga conveniente {@link #despachar(Incidente, Iterable,
   * cl.ucen.sentinel.domain.routing.GrafoVial)}.
   */
  public static final CalculadorRuta DEFAULT_ROUTER = AEstrella::aEstrella;

  // ---------------------------------------------------------------------------
  // Tipos internos
  // ---------------------------------------------------------------------------

  /**
   * Par tiempos-rutas producido por {@link #calcularTiemposViaje}.
   *
   * @param tiempos mapa {@code unidad.id -> T_viaje_s}; {@code Double.POSITIVE_INFINITY} cuando A*
   *     lanzó {@link NoRutaDisponibleException}
   * @param rutas mapa {@code unidad.id -> lista de nodos} solo para unidades con ruta disponible
   */
  record TiemposYRutas(Map<String, Double> tiempos, Map<String, List<Long>> rutas) {}

  // ---------------------------------------------------------------------------
  // API pública
  // ---------------------------------------------------------------------------

  /**
   * Caso de uso principal: despacha la mejor unidad para un incidente.
   *
   * <p>Espejo del Python {@code despachar(incidente, flota, grafo, ...)} en {@code
   * application/despachar_ambulancia.py}.
   *
   * @param incidente incidente ya triado y con coordenadas validadas
   * @param flota lista completa de la flota SAMU (cualquier estado); las unidades en TALLER se
   *     excluyen automáticamente (RN-04)
   * @param grafo implementación del puerto {@link cl.ucen.sentinel.domain.routing.GrafoVial}
   *     (típicamente el adapter GraphML; en tests, un fake)
   * @param factorHora multiplicador de tráfico horario para el A* (SRS sec. 2.6-B); {@code 1.0} =
   *     sin penalización
   * @param factorSirena multiplicador de sirena para el A* (≤ 1.0 acelera; {@code 1.0} desactivado)
   * @param progresoPorUnidad mapeo opcional {@code unidad.id -> progresoPct} para las unidades
   *     EnRuta; se usa cuando hay saturación para ordenar candidatas a re-dirección (RN-08, CP-10);
   *     {@code null} equivale a mapa vacío
   * @param router implementación del cálculo de ruta a usar (inyectable para tests)
   * @return {@link ResultadoDespacho} con el motivo (OPTIMO / PENALIZADO / SUBOPTIMO_RN02 /
   *     SATURACION), la unidad elegida (o {@code null}), el desglose del costo, todos los
   *     candidatos evaluados y, si aplica, el estado de saturación con candidatas a re-dirección
   */
  public static ResultadoDespacho despachar(
      Incidente incidente,
      Iterable<Unidad> flota,
      cl.ucen.sentinel.domain.routing.GrafoVial grafo,
      double factorHora,
      double factorSirena,
      Map<String, Double> progresoPorUnidad,
      CalculadorRuta router) {

    List<Unidad> flotaLista =
        StreamSupport.stream(flota.spliterator(), false)
            .collect(java.util.stream.Collectors.toList());

    TiemposYRutas ty =
        calcularTiemposViaje(flotaLista, incidente, grafo, factorHora, factorSirena, router);

    List<Unidad> disponibles = new ArrayList<>();
    for (Unidad u : flotaLista) {
      if (u.estado() == EstadoUnidad.DISPONIBLE) {
        disponibles.add(u);
      }
    }

    ResultadoSeleccion seleccion =
        Seleccion.seleccionarUnidad(disponibles, incidente, ty.tiempos());

    // Caso ganador: argmin encontró elegida con costo finito
    if (seleccion.elegida() != null && seleccion.costoElegida() != null) {
      MotivoDespacho motivo =
          seleccion.costoElegida().penalizacion() > 0.0
              ? MotivoDespacho.PENALIZADO
              : MotivoDespacho.OPTIMO;
      List<Long> ruta = ty.rutas().getOrDefault(seleccion.elegida().id(), List.of());
      return new ResultadoDespacho(
          incidente,
          seleccion.elegida(),
          seleccion.costoElegida(),
          motivo,
          false,
          seleccion.candidatos(),
          null,
          ruta);
    }

    // Caso fallback RN-02: hay disponibles pero argmin retornó null (todas tienen costo ∞)
    if (!disponibles.isEmpty()) {
      Optional<CandidatoDespacho> fallbackOpt =
          fallbackRn02Basica(disponibles, incidente, ty.tiempos());
      if (fallbackOpt.isPresent()) {
        CandidatoDespacho candidato = fallbackOpt.get();
        LOG.warning(
            String.format(
                "RN-02 fallback aplicado: %s (Básica) → %s (%s); despachoSuboptimo=true",
                candidato.unidad().id(), incidente.id(), incidente.categoriaMpds().valor()));
        List<Long> ruta = ty.rutas().getOrDefault(candidato.unidad().id(), List.of());
        return new ResultadoDespacho(
            incidente,
            candidato.unidad(),
            candidato.costo(),
            MotivoDespacho.SUBOPTIMO_RN02,
            true,
            seleccion.candidatos(),
            null,
            ruta);
      }
    }

    // Caso saturación: no hay disponibles o no hay fallback viable
    EstadoSaturacion estadoSat = Saturacion.detectar(flotaLista, progresoPorUnidad);
    return new ResultadoDespacho(
        incidente,
        null,
        null,
        MotivoDespacho.SATURACION,
        false,
        seleccion.candidatos(),
        estadoSat,
        List.of());
  }

  /**
   * Sobrecarga conveniente con valores por defecto: {@code factorHora=1.0}, {@code
   * factorSirena=1.0}, {@code progresoPorUnidad=null}, {@code router=AEstrella::aEstrella}.
   *
   * @param incidente incidente ya triado y con coordenadas validadas
   * @param flota lista completa de la flota SAMU (cualquier estado)
   * @param grafo implementación del puerto GrafoVial
   * @return {@link ResultadoDespacho}
   */
  public static ResultadoDespacho despachar(
      Incidente incidente,
      Iterable<Unidad> flota,
      cl.ucen.sentinel.domain.routing.GrafoVial grafo) {
    return despachar(incidente, flota, grafo, 1.0, 1.0, null, DEFAULT_ROUTER);
  }

  // ---------------------------------------------------------------------------
  // Helpers privados
  // ---------------------------------------------------------------------------

  /**
   * Calcula {@code T_viaje} y ruta de nodos desde la base de cada unidad hacia el incidente.
   *
   * <p>Snap del incidente y de cada base. Las unidades en TALLER se omiten silenciosamente (RN-04).
   * Si {@link CalculadorRuta#calcular} lanza {@link NoRutaDisponibleException}, el tiempo se
   * registra como {@code Double.POSITIVE_INFINITY} y la ruta queda ausente del mapa {@code rutas}
   * (semántica "sin ruta"). Esas unidades nunca son elegidas como ganadoras.
   *
   * @param flota lista de unidades (puede incluir TALLER)
   * @param incidente evento con coordenadas validadas
   * @param grafo puerto GrafoVial para snaps y aristas
   * @param factorHora multiplicador horario para el A*
   * @param factorSirena multiplicador de sirena para el A*
   * @param router implementación del cálculo de ruta
   * @return {@link TiemposYRutas} con los dos mapas
   */
  static TiemposYRutas calcularTiemposViaje(
      Iterable<Unidad> flota,
      Incidente incidente,
      cl.ucen.sentinel.domain.routing.GrafoVial grafo,
      double factorHora,
      double factorSirena,
      CalculadorRuta router) {

    long nodoIncidente = grafo.nodoMasCercano(incidente.lat(), incidente.lon());
    Map<String, Double> tiempos = new HashMap<>();
    Map<String, List<Long>> rutas = new HashMap<>();

    for (Unidad unidad : flota) {
      if (unidad.estado() == EstadoUnidad.TALLER) {
        continue;
      }
      try {
        long nodoBase = grafo.nodoMasCercano(unidad.baseLat(), unidad.baseLon());
        AEstrella.Resultado resultado =
            router.calcular(grafo, nodoBase, nodoIncidente, factorHora, factorSirena);
        tiempos.put(unidad.id(), resultado.etaSegundos());
        rutas.put(unidad.id(), resultado.rutaNodos());
      } catch (NoRutaDisponibleException e) {
        tiempos.put(unidad.id(), Double.POSITIVE_INFINITY);
      }
    }

    return new TiemposYRutas(tiempos, rutas);
  }

  /**
   * Si aplica RN-02, elige la Básica disponible de menor {@code T_viaje}.
   *
   * <p>Espejo del Python {@code _fallback_rn02_basica} en {@code
   * application/despachar_ambulancia.py}.
   *
   * @param disponibles lista de unidades en estado DISPONIBLE
   * @param incidente evento triado
   * @param tiempos mapa {@code unidad.id -> T_viaje_s}
   * @return {@link Optional} con el {@link CandidatoDespacho} de la Básica elegida, o vacío si el
   *     fallback no aplica (categoría no es Echo/Delta, no hay Básicas disponibles, o ninguna tiene
   *     ruta finita)
   */
  private static Optional<CandidatoDespacho> fallbackRn02Basica(
      List<Unidad> disponibles, Incidente incidente, Map<String, Double> tiempos) {

    if (!CATEGORIAS_CRITICAS_RN02.contains(incidente.categoriaMpds())) {
      return Optional.empty();
    }

    List<Unidad> basicas = new ArrayList<>();
    for (Unidad u : disponibles) {
      if (u.tipo() == TipoUnidad.BASICA) {
        basicas.add(u);
      }
    }
    if (basicas.isEmpty()) {
      return Optional.empty();
    }

    // Solo Básicas con tiempo finito
    List<Map.Entry<Unidad, Double>> basicasConRuta = new ArrayList<>();
    for (Unidad u : basicas) {
      Double t = tiempos.get(u.id());
      if (t != null && Double.isFinite(t)) {
        basicasConRuta.add(Map.entry(u, t));
      }
    }
    if (basicasConRuta.isEmpty()) {
      return Optional.empty();
    }

    // Ordenar por (tViaje asc, id asc)
    basicasConRuta.sort(
        (a, b) -> {
          int cmpT = Double.compare(a.getValue(), b.getValue());
          if (cmpT != 0) return cmpT;
          return a.getKey().id().compareTo(b.getKey().id());
        });

    Unidad elegida = basicasConRuta.get(0).getKey();
    double tViaje = basicasConRuta.get(0).getValue();

    // Calcular el costo real (penalización ∞ para Echo/Delta + Básica → esInfinito=true)
    CostoDespacho costoReal = FuncionCosto.costo(elegida, incidente, tViaje);
    return Optional.of(new CandidatoDespacho(elegida, tViaje, costoReal));
  }
}
