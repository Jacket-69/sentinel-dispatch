package cl.ucen.sentinel.domain.routing;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.PriorityQueue;

/**
 * Algoritmo A* puro sobre el puerto {@link GrafoVial} (ADR-0010 §1).
 *
 * <p>Espejo bit-exacto del Python {@code a_estrella} en {@code
 * sentinel_dispatch/domain/routing/a_estrella.py}. El tie-breaker {@code (f, contador, nodo)}
 * replica el comportamiento del {@code heapq} Python: en empate de {@code f}, el menor {@code
 * contador} gana (FIFO entre empates). {@code contador} se incrementa en cada {@code heappush},
 * igual que en el Python.
 *
 * <p>NO usa {@code AStarShortestPath} de JGraphT porque su política de desempate no coincide con
 * {@code heapq}, lo que rompería la validación dual RT-02 sobre rutas con {@code f_score} igual
 * entre candidatos.
 *
 * <p>Lógica pura: depende solo de {@link GrafoVial}, {@link Heuristica} y stdlib Java.
 */
public final class AEstrella {

  private AEstrella() {}

  /**
   * Resultado del A*: tiempo de viaje óptimo y ruta de nodos.
   *
   * @param etaSegundos tiempo de viaje óptimo en segundos
   * @param rutaNodos lista de identificadores de nodo en orden origen → destino (ambos incluidos)
   */
  public record Resultado(double etaSegundos, List<Long> rutaNodos) {}

  /**
   * Calcula la ruta de menor tiempo entre dos nodos del grafo vial usando A* con heurística
   * Haversine admisible.
   *
   * <p>Espejo de {@code a_estrella(grafo, origen, destino, factor_hora, factor_sirena)} Python.
   *
   * @param grafo instancia del puerto GrafoVial, solo lectura
   * @param origen identificador OSM del nodo de partida
   * @param destino identificador OSM del nodo de llegada
   * @param factorHora multiplicador por franja horaria (&gt; 0); actúa como multiplicador de la
   *     velocidad efectiva (igual que Python: denominador conjunto con factorSirena)
   * @param factorSirena multiplicador por estado de sirena (&gt; 0); actúa como multiplicador de la
   *     velocidad efectiva junto a factorHora
   * @return {@link Resultado} con {@code etaSegundos} y {@code rutaNodos}
   * @throws IllegalArgumentException si {@code factorHora <= 0} o {@code factorSirena <= 0}
   * @throws NoRutaDisponibleException si no existe camino entre origen y destino
   */
  public static Resultado aEstrella(
      GrafoVial grafo, long origen, long destino, double factorHora, double factorSirena) {

    if (factorHora <= 0) {
      throw new IllegalArgumentException("factorHora debe ser > 0, recibido: " + factorHora);
    }
    if (factorSirena <= 0) {
      throw new IllegalArgumentException("factorSirena debe ser > 0, recibido: " + factorSirena);
    }

    if (origen == destino) {
      return new Resultado(0.0, List.of(origen));
    }

    GrafoVial.Coordenadas coordDestino = grafo.coordenadas(destino);
    double latDestino = coordDestino.lat();
    double lonDestino = coordDestino.lon();

    // g_score[n] = costo real mínimo conocido desde origen hasta n
    Map<Long, Double> gScore = new HashMap<>();
    gScore.put(origen, 0.0);

    // padre[n] = nodo predecesor en el camino óptimo hasta n
    Map<Long, Long> padre = new HashMap<>();

    // Heap: HeapEntry(f, contador, nodo) — tie-breaker replica heapq Python
    long contador = 0L;
    GrafoVial.Coordenadas coordOrigen = grafo.coordenadas(origen);
    double hOrigen =
        Heuristica.haversineSegundos(coordOrigen.lat(), coordOrigen.lon(), latDestino, lonDestino);
    PriorityQueue<HeapEntry> openSet = new PriorityQueue<>();
    openSet.add(new HeapEntry(hOrigen, contador, origen));

    while (!openSet.isEmpty()) {
      HeapEntry actual = openSet.poll();
      long nodoActual = actual.nodo();

      // Lazy decrease-key: ignorar entradas obsoletas del heap
      double gActual = gScore.getOrDefault(nodoActual, Double.MAX_VALUE);
      GrafoVial.Coordenadas coordActual = grafo.coordenadas(nodoActual);
      double hActual =
          Heuristica.haversineSegundos(
              coordActual.lat(), coordActual.lon(), latDestino, lonDestino);
      if (actual.f() > gActual + hActual) {
        continue;
      }

      if (nodoActual == destino) {
        return new Resultado(gActual, reconstruirRuta(padre, origen, destino));
      }

      for (GrafoVial.Arista arista : grafo.vecinos(nodoActual)) {
        // Costo de arista: longitud_m / (velocidad_m/s * factor_hora * factor_sirena)
        // Replica: velocidad_ms = velocidad_efectiva_kmh * 1000.0 / 3600.0
        //          peso = longitud_m / (velocidad_ms * factor_hora * factor_sirena)
        double velocidadMs = arista.velocidadEfectivaKmh() * 1000.0 / 3600.0;
        double peso = arista.longitudM() / (velocidadMs * factorHora * factorSirena);

        double gTentativo = gActual + peso;
        long vecino = arista.destino();

        if (gTentativo < gScore.getOrDefault(vecino, Double.MAX_VALUE)) {
          gScore.put(vecino, gTentativo);
          padre.put(vecino, nodoActual);

          GrafoVial.Coordenadas coordVecino = grafo.coordenadas(vecino);
          double hVecino =
              Heuristica.haversineSegundos(
                  coordVecino.lat(), coordVecino.lon(), latDestino, lonDestino);
          double fVecino = gTentativo + hVecino;
          contador++;
          openSet.add(new HeapEntry(fVecino, contador, vecino));
        }
      }
    }

    throw new NoRutaDisponibleException(origen, destino);
  }

  /**
   * Reconstruye la ruta desde destino hasta origen recorriendo el mapa padre y la invierte.
   *
   * <p>Espejo de {@code _reconstruir_ruta} Python.
   *
   * @param padre mapa nodo → predecesor en el camino óptimo
   * @param origen nodo de partida
   * @param destino nodo de llegada
   * @return lista de IDs en orden origen → destino
   */
  private static List<Long> reconstruirRuta(Map<Long, Long> padre, long origen, long destino) {
    List<Long> ruta = new ArrayList<>();
    long nodo = destino;
    while (nodo != origen) {
      ruta.add(nodo);
      nodo = padre.get(nodo);
    }
    ruta.add(origen);
    Collections.reverse(ruta);
    return ruta;
  }

  /**
   * Entrada del heap con tie-breaker determinista.
   *
   * <p>Ordena por {@code f} ascendente; en empate, por {@code contador} ascendente (FIFO). Replica
   * la semántica de las tuplas {@code (f, contador, nodo)} de {@code heapq} Python.
   *
   * @param f f-score de la entrada
   * @param contador contador de inserción (se incrementa en cada push)
   * @param nodo identificador OSM del nodo
   */
  private record HeapEntry(double f, long contador, long nodo) implements Comparable<HeapEntry> {
    @Override
    public int compareTo(HeapEntry otro) {
      int cmpF = Double.compare(this.f, otro.f);
      if (cmpF != 0) {
        return cmpF;
      }
      return Long.compare(this.contador, otro.contador);
    }
  }
}
