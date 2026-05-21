---
adr: 0019
title: Spike CP-12 — criterio de rendimiento ajustado a evidencia empírica
status: accepted
date: 2026-05-21
deciders: Benjamin López
tags: [adr, rendimiento, spike, h4]
---

# ADR 0019 — Spike CP-12 y criterio de rendimiento ajustado

## Contexto

El SRS sec. 2.13 (CP-12) y RN-05 piden que el orquestador de despacho ejecute en **≤ 1000 ms** para una flota de 50 unidades. Hasta H3 la métrica nunca se midió empíricamente: el número provino del documento original y no se validó contra la implementación real.

La convención del proyecto ([CONTRIBUTING.md](../../../CONTRIBUTING.md) §"spike-before-CP", aplicada antes en [ADR-0011](0011-reformulacion-criterio-it01.md)) exige medir **antes** de comprometerse con un criterio numérico. Si el spike falla, el ADR documenta el delta y propone un criterio realista, en lugar de prometer algo que el código no sostiene.

Este ADR ejecuta el spike sobre `application.despachar_ambulancia.despachar(...)` con la flota sintética definida en `tools/spike_cp12_performance.py` y congela el resultado.

## Decisión

**Adoptamos un criterio CP-12 ajustado a ≤ 2000 ms p95 para 50 unidades** sobre el grafo `data/graphs/coquimbo.graphml` (16 679 nodos / 42 508 aristas). El criterio del SRS (≤ 1000 ms) **no se cumple** con la implementación actual (A* secuencial por unidad); el ajuste refleja la realidad medida y la documenta para futuros consumidores.

### Resultado del spike (corrida 2026-05-21)

Comando: `uv run --project core-python python tools/spike_cp12_performance.py`.

Configuración:
- 50 unidades sintéticas (30 Avanzada / 20 Básica) en grilla regular sobre bbox conurbación La Serena-Coquimbo (`lat ∈ [-30.05, -29.85]`, `lon ∈ [-71.45, -71.20]`).
- 1 incidente Echo en el centro de la bbox.
- 10 repeticiones warm-cache tras un run de calentamiento.
- Carga del grafo (~1.28 s) **excluida** del wall-clock.

| Métrica | Valor (ms) |
|---|---|
| p50 | 1884.6 |
| p95 | 1941.6 |
| max | 1975.1 |
| media | 1895.8 |

Resultado crudo persistido en `tools/_out/spike_cp12_resultado.json`.

**Veredicto**: con criterio SRS (≤ 1000 ms p95) → FALLA. Con criterio ajustado (≤ 2000 ms p95) → PASA.

### Análisis del costo dominante

El cuello de botella es el A*: 50 invocaciones secuenciales sobre un grafo de ~16 K nodos. Cada A* toma ~37 ms en promedio (1900 ms / 50). Esto está alineado con la cota individual medida en H2 (~70 ms para A* end-to-end sobre rutas largas; para flotas distribuidas en grilla las rutas son más cortas).

El snap por barrido (Haversine) no es bottleneck (~0.5 ms por nodo); la serialización a `CostoDespacho` y el `argmin` son despreciables.

## Alternativas consideradas

### Mantener criterio SRS ≤ 1000 ms y paralelizar A* con `ProcessPoolExecutor`

- **Pros**: cumple SRS al pie de la letra; el orquestador acelera 4-8× con cores ociosos.
- **Contras**:
  - Requiere refactor de `_calcular_tiempos_viaje` a multiprocesos.
  - Serializar el grafo (~21 MB) a cada worker via pickle es prohibitivo; necesita memoria compartida (`multiprocessing.shared_memory` o leer cada worker del archivo).
  - GIL bloquea threads para A* puro Python; ThreadPoolExecutor no ayuda.
  - Costo de implementación: ~1-2 días dev + tests; riesgo de regresión en paridad RT-02 si el orden de relajación cambia.
- **Por qué se descarta para v1**: el SRS no exige paralelismo. Ajustar el criterio refleja honestamente la implementación y permite cerrar H4 sin abrir un frente de optimización mayor. Reconsiderar si v2 lo demanda.

### Reducir N a 25 unidades y mantener ≤ 1000 ms

- **Pros**: el criterio se cumple (~950 ms estimado para 25 unidades).
- **Contras**: cambiar el N rompe la equivalencia conceptual con el SRS. El SRS habla de "flota de 50 unidades" porque ese es el orden de magnitud de SAMU IV Región según data pública. Bajar a 25 oculta el problema.
- **Por qué se descarta**: integridad del experimento. Mejor reconocer el delta que esconderlo.

### Migrar el A* a Rust/C via PyO3

- **Pros**: aceleración 10-50×; cumple ≤ 1000 ms con margen.
- **Contras**: dependencia nueva pesada; toolchain Rust en CI; complejidad de mantenimiento; ROI académico negativo (un ramo no debería requerir Rust para cumplir un CP de tiempo).
- **Por qué se descarta**: violación clara del principio "no agregar dependencias pesadas sin justificación" (CLAUDE.md anti-fricciones).

### Cachear A* por (origen, destino, factor_hora, factor_sirena)

- **Pros**: ejecuciones repetidas del mismo orquestador son virtualmente gratis.
- **Contras**: el caso de uso es "despacho one-shot", no batch; la cache no se amortiza en operación real.
- **Por qué se descarta**: optimización sin contexto operativo que la justifique.

## Consecuencias

### Positivas

- **El criterio CP-12 queda verificable y verificado**: el test `test_performance_50_unidades.py` (marker `slow`) lo ejecuta on-demand.
- **El delta SRS↔implementación queda documentado**: futuras lecturas del SRS deben cruzarse con este ADR para tener el criterio realista.
- **Defensa académica reforzada**: tener un spike con números concretos vale más que un criterio sobreoptimista pero no validado.

### Negativas / costo

- **El criterio del SRS no se cumple literalmente**. Si el profesor evalúa contra el SRS sin leer el ADR, perdemos puntos. Mitigación: la matriz de trazabilidad (`docs/quality/trazabilidad.md`) referencia explícitamente este ADR en la celda CP-12 / RN-05.
- **Paralelización queda como deuda técnica** abierta para v2.

### Neutras

- El test de performance se marca `@pytest.mark.slow` y NO corre en `make test-fast` ni en CI por default. Se invoca con `pytest -m slow` cuando se quiere validar performance.

## Cumplimiento / verificación

- `tools/spike_cp12_performance.py` — script reproducible del spike.
- `tools/_out/spike_cp12_resultado.json` — resultado de la corrida congelada (2026-05-21).
- `core-python/tests/integration/test_performance_50_unidades.py` — test con marker `slow` que valida `p95 ≤ 2000 ms` contra el criterio ajustado.
- `docs/quality/trazabilidad.md` — RN-05 y CP-12 referencian este ADR con el criterio ajustado.

## Referencias

- [SRS sec. 2.13 — CP-12](../../SRS.md) — criterio original.
- [CONTRIBUTING.md](../../../CONTRIBUTING.md) §"spike-before-CP".
- [ADR-0011](0011-reformulacion-criterio-it01.md) — precedente de criterio ajustado por evidencia empírica.
- [ADR-0014](0014-funcion-costo-dispatch.md), [ADR-0015](0015-fallback-rn02-suboptimo.md) — el orquestador medido.
