package cl.ucen.sentinel.application;

import cl.ucen.sentinel.domain.routing.AEstrella;
import cl.ucen.sentinel.domain.routing.GrafoVial;
import cl.ucen.sentinel.domain.routing.NoRutaDisponibleException;

/**
 * Puerto funcional para el cálculo de ruta entre dos nodos del grafo vial.
 *
 * <p>Permite inyectar implementaciones alternativas al orquestador {@link DespacharAmbulancia}, en
 * particular fakes deterministicos en tests sin necesidad de {@code monkeypatch}. La implementación
 * de producción es la method reference {@code AEstrella::aEstrella}.
 *
 * <p>Al ser un {@link FunctionalInterface}, cualquier lambda que matchee la firma sirve como
 * implementación. Ejemplo de uso en tests:
 *
 * <pre>{@code
 * CalculadorRuta fake = (grafo, origen, destino, fh, fs) -> {
 *     Double t = tiempos.get(unidadIdPorNodo.get(origen));
 *     if (t == null || Double.isInfinite(t)) throw new NoRutaDisponibleException(origen, destino);
 *     return new AEstrella.Resultado(t, List.of(origen, destino));
 * };
 * }</pre>
 *
 * <p>Fuente normativa: ADR-0014, ADR-0015. Decisión de diseño: inyección funcional en lugar de
 * subclase o Mockito para mantener tests sin dependencias de mocking adicionales.
 */
@FunctionalInterface
public interface CalculadorRuta {

  /**
   * Calcula la ruta de menor tiempo entre {@code origen} y {@code destino}.
   *
   * @param grafo instancia del puerto GrafoVial, solo lectura
   * @param origen identificador OSM del nodo de partida (snap de la base de la unidad)
   * @param destino identificador OSM del nodo de destino (snap del incidente)
   * @param factorHora multiplicador por franja horaria ({@literal >} 0)
   * @param factorSirena multiplicador por estado de sirena ({@literal >} 0)
   * @return {@link AEstrella.Resultado} con tiempo en segundos y lista de nodos
   * @throws NoRutaDisponibleException si no existe camino entre origen y destino
   */
  AEstrella.Resultado calcular(
      GrafoVial grafo, long origen, long destino, double factorHora, double factorSirena);
}
