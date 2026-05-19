---
adr: 0016
title: Camino al 95% de confianza sobre CP-01a — calibración (Ruta A) + fixture v3 (Ruta B)
status: proposed
date: 2026-05-19
deciders: Benjamín López
tags: [adr, dominio, routing, it01, osrm, srs, validacion, bootstrap, calibracion]
---

# ADR 0016 — Camino al 95% de confianza sobre CP-01a

## Contexto

[ADR-0011](0011-reformulacion-criterio-it01.md) §Verdad/Limitaciones #5 reconoce que CP-01a se cumple por **margen estrecho**: 78/100 contra mínimo 75/100. PR #11 cuantificó esa observación con un **bootstrap no paramétrico** (B=1000, semilla=2026, ver [`docs/quality/bootstrap-cp01a.md`](../../quality/bootstrap-cp01a.md)):

- Mediana bootstrap: **78**.
- **IC95 = [69, 86]**.
- P(conteo ≥ 75 en una réplica) = **78.9%**.

Como el IC95 inferior (69) está por debajo del mínimo (75), CP-01a **no es defendible al 95% de confianza estadística** — solo al ~79%. Ese 79% es honesto pero no es la convención académica de "robustez empírica" en validación de algoritmos.

La pregunta natural en la defensa GCS y en revisiones posteriores es:

> *¿Cuál es el plan para alcanzar el 95%?*

Los ADRs previos cubren parcialmente la respuesta:

- [ADR-0011](0011-reformulacion-criterio-it01.md) §"Decisión a futuro" lista tres mejoras incrementales al A* (calibración, turn penalties, snap-to-edge) como condicionales a hallazgos en H4/H5.
- [ADR-0013](0013-cp01c-criterio-calibrado.md) formaliza dos de esas mejoras como tareas H4-cal-1/2/eval, con criterio CP-01c (duration ±15% en ≥85/100).

Pero ninguno de los dos:

1. Ata explícitamente las mejoras al criterio bootstrap-IC95 ≥ 75 al 95%.
2. Discute la **vía complementaria** de ampliar el fixture (más pares) para apretar la varianza del bootstrap.

Este ADR cierra esa brecha: define un **plan combinado** y un **criterio de éxito assertable y bootstrap-derivado**.

## Marco analítico — dos rutas matemáticas al 95%

El IC95 inferior debe cumplir `lo ≥ 75`. Hay dos formas de mover esa cota hacia arriba sobre la métrica CP-01a:

**Ruta A — subir la mediana** (mover el centro del intervalo hacia la derecha)

Mejorar el algoritmo A* propio para que más pares caigan dentro de la tolerancia `|Δ_distance|/d_OSRM ≤ 0.30`. Cada mejora reduce el número de outliers atribuidos a una de las cinco causas identificadas en ADR-0011 §Diagnóstico:

- `factor_calibracion = 0.85` (mimetiza speed factor de OSRM) — afecta principalmente duration, indirectamente distance vía rutas elegidas.
- Turn penalties simples (~2 s por giro >30°) — redistribuye rutas y reduce el ~18% residual.
- Snap-to-edge con interpolación — elimina el ~68% de outliers atribuidos a `snap_endpoints` y `snap_corto` ([`docs/quality/outliers-sensibilidad.md`](../../quality/outliers-sensibilidad.md)).

Estimación: si las tres se aplican, la mediana del conteo bootstrap subiría de **78** hacia **85-90**, lo que arrastra el IC95 inferior por encima de 75 con holgura.

**Ruta B — apretar el ancho** (estrechar el intervalo)

Si el conteo `X` sigue aproximadamente `Binomial(N, p)` con `p ≈ 0.78` (fracción real), la desviación estándar de la fracción `X/N` es `σ_frac = √(p(1−p)/N) ≈ √(0.1716/N)`. El ancho del IC95 normal sobre la fracción es `≈ 2·1.96·σ_frac`. Expresado como porcentaje (fracción × 100) para mantener comparabilidad con el conteo actual:

| N | σ_frac | Ancho IC95 (puntos %) | IC95 fracción si mediana = 0.78 |
|---:|---:|---:|---|
| 100 | 0.041 | **16.2** | [0.70, 0.86] |
| 300 | 0.024 |  9.4 | [0.74, 0.83] |
| 500 | 0.019 |  7.3 | [0.75, 0.81] |

(La fila N=100 calza bien con el bootstrap empírico [69,86], ancho 17.)

Es decir: aun manteniendo la fracción en 0.78, con N=300 el IC95 inferior llega a 0.74 (justo por debajo del 0.75); con N=500 raspa el 0.75. Solo con Ruta B **probablemente no alcanza**; es complemento, no sustituto.

**Conclusión analítica**: la única vía robusta al 95% es **A + B combinadas**. A mueve la mediana hacia arriba (deja margen), B aprieta el ancho (transforma el margen en cumplimiento estadístico).

## Decisión

Adoptamos el plan **A + B** con criterio de éxito bootstrap-assertable:

### Definición del criterio CP-01a-95 (objetivo)

Tras ejecutar Ruta A + Ruta B, regenerar el bootstrap de la **fracción** "dentro de tolerancia" (`fracción = conteo / N`) con los mismos parámetros que PR #11 (B=1000, semilla=2026, tolerancia=0.30) sobre el fixture v3 ampliado de tamaño N. **CP-01a-95** se considera cumplido si ambas condiciones aplican:

$$
\text{IC}_{95}^{\text{inferior}}(\text{fracción}) \ge 0.75 \quad \text{Y} \quad P(\text{fracción} \ge 0.75) \ge 0.95
$$

Es decir: el percentil 2.5 de la distribución bootstrap de la fracción dentro de tolerancia debe ser ≥ 0.75, equivalentemente el 95% inferior de las réplicas debe cumplir CP-01a. La métrica usa fracción (no conteo absoluto) para que el criterio sea independiente de N y permita comparar v2 (N=100) con v3 (N=300+) en la misma escala.

El criterio es **medible reejecutando `tools/bootstrap_cp01a.py`** — no requiere literatura externa ni juicio subjetivo. Requiere un cambio menor en el script para reportar IC95 sobre fracción además del conteo absoluto.

### Ruta A — calibración del A* (referencia ADR-0013)

Sin cambios respecto a [ADR-0013](0013-cp01c-criterio-calibrado.md). Tres tareas:

1. **H4-cal-1**: aplicar `factor_calibracion = 0.85` al adapter `OsmnxGrafoVial` o al loader del grafo.
2. **H4-cal-2**: modelar turn penalties simples en `domain/routing/a_estrella.py`.
3. **H4-cal-eval**: re-correr `test_routing_vs_osrm.py` con ambos cambios.

Adicionalmente, este ADR-0016 promueve la mejora 3 del ADR-0011 §"Decisión a futuro" de *stretch* a **obligatoria** para alcanzar CP-01a-95:

4. **H5-cal-3**: implementar snap-to-edge con interpolación en `OsmnxGrafoVial`. Requiere reescribir `nodo_mas_cercano` como `arista_mas_cercana` con `interpolar_punto_en_arista`. Impacto en API del puerto `GrafoVial`: agregar método `coord_a_posicion_en_arista(lat, lon) → (arista, fraccion)`. Estimación: ~6-8 h.

### Ruta B — fixture v3 con N ≥ 300

Generar un fixture nuevo `tests/fixtures/osrm_oracle_v3.json` con mayor diversidad y volumen de pares. Tareas:

5. **H5-fix-1**: extender `tools/generate_osrm_fixture.py` con dos flags nuevos:
    - `--modo {basesxincidentes, cartesiano}` — alternar entre la generación actual (10 bases × 12 incidentes × 10 jitters) y un producto cartesiano sobre el bbox `(-71.45, -30.10, -71.15, -29.85)` con jitter amplio (`radio_grados=0.01°` ≈ 1.1 km).
    - `--n-objetivo <int>` — objetivo de pares válidos (default 100, target 300).

6. **H5-fix-2**: regenerar el fixture con `--modo cartesiano --n-objetivo 300` contra OSRM 5.27.1 Docker. Committear como `tests/fixtures/osrm_oracle_v3.json` (mantener `osrm_oracle.json` v2 sin tocar, para preservar la línea histórica del experimento original).

7. **H5-fix-3**: parametrizar `tools/bootstrap_cp01a.py` con `--fixture <path>` (ya existe) y `tools/analyze_outliers.py` similar. Re-correr ambos contra v3.

### Validación final — H5-eval-95

8. **H5-eval-95**: ejecutar `uv run --project core-python python tools/bootstrap_cp01a.py --fixture tests/fixtures/osrm_oracle_v3.json` tras aplicar Ruta A + Ruta B. Assertear:
    - `IC95 inferior ≥ 75`
    - `P(conteo ≥ 75) ≥ 0.95`

   Si ambas se cumplen, marcar ADR-0016 como `accepted`, marcar ADR-0011 §V/L#5 como `resuelto`, actualizar matriz de trazabilidad RF-03 y, opcionalmente, agregar test de integración `test_bootstrap_cp01a_95.py` que automatice el chequeo en CI.

## Alternativas consideradas

### Opción 1 — Solo Ruta A (sin fixture v3)

- **Pros**: ya está descompuesto en ADR-0013, menos esfuerzo total (~3-5h por tarea, sin Docker para Ruta A en sí, solo para validación).
- **Contras**: con N=100 el ancho del IC95 se mantiene en ~17 pares. Aun si la mediana sube a 88, el IC95 inferior sería ~80 — cumple pero por margen menor. Si la mejora del algoritmo es menor a lo proyectado (p. ej. mediana sube solo a 82), el IC95 inferior queda en ~74, casi cumpliendo. Frágil.
- **Por qué se descartó**: defensivamente más débil — si la calibración no rinde lo esperado, no hay backup. Ampliar fixture es barato relativo al beneficio.

### Opción 2 — Solo Ruta B (sin calibración)

- **Pros**: ~2h con Docker activo. No requiere tocar el código de dominio.
- **Contras**: con mediana 78, ni con N=500 se alcanza IC95 inferior 75 con holgura (queda en 74-75 raspando). Más allá: el bootstrap sobre un fixture con jitter amplio puede *bajar* la mediana si los pares cartesianos exponen más rutas difíciles, lo que **empeora** el resultado.
- **Por qué se descartó**: matemáticamente insuficiente; arriesga deteriorar el resultado actual.

### Opción 3 — Reescritura del A* a edge-expanded turn-based (mencionada en ADR-0011)

- **Pros**: cumple el criterio CP-01 ±5% original del SRS.
- **Contras**: 1-2 semanas de esfuerzo, fuera del cronograma académico H4/H5.
- **Por qué se descartó**: alcance excede ramo GCS; queda como nota a futuro fuera del proyecto.

## Cumplimiento / verificación

- Cada tarea de Ruta A y Ruta B se ejecuta en su propio PR con tests verde.
- El criterio CP-01a-95 es **automatizable**: la verificación final es una corrida de `tools/bootstrap_cp01a.py` con los flags adecuados. El output (IC95 + P(≥75)) se compara contra los umbrales numéricos definidos arriba.
- Si CP-01a-95 falla por márgenes razonables (ej. P=0.93 en vez de 0.95), abrir ADR-0017 documentando el resultado y decidiendo: aceptar el 93% como "cota inferior cuantificada", o invertir en mejoras adicionales.

## Consecuencias

### Positivas

- La defensa GCS y revisiones post-H5 pueden responder *"¿plan para llegar al 95%?"* con un ADR concreto, criterio numérico assertable y descomposición en 8 tareas.
- El criterio CP-01a-95 está derivado del experimento, no impuesto a priori — viene de la matemática del bootstrap (PR #11).
- Ruta A + Ruta B son **ortogonales**: pueden ejecutarse en paralelo (calibración no depende de fixture v3 ni viceversa).
- Fixture v3 sirve a múltiples propósitos: aborda también ADR-0011 §V/L#3 (sesgo del jitter) y §V/L#6 (aislamiento de causas), no solo el margen al 95%.

### Negativas / costo

- ~10-15 h de esfuerzo agregado distribuido entre H4 y H5. Riesgo de retrasar H5 (informe final, deadline 2026-07-15) si las tareas se acumulan.
- Snap-to-edge (H5-cal-3) requiere cambiar la firma del puerto `GrafoVial`, lo que toca tests del módulo `routing` y posiblemente del `dispatch`. Es refactor con superficie no trivial.
- Fixture v3 requiere Docker activo para regenerar OSRM. Si el equipo pierde acceso a Docker en H5, la Ruta B se bloquea.
- Compromiso público: si CP-01a-95 no se alcanza, hay que documentar el fracaso (vía ADR-0017) — más superficie de defensa.

### Neutras

- ADR queda en `status: proposed` hasta que H5-eval-95 se ejecute. Las tareas individuales pueden completarse y marcarse antes (cada tarea actualiza este ADR con su estado).
- Este ADR **complementa** ADR-0013 (no lo supersede). ADR-0013 sigue siendo válido para el criterio CP-01c (duration ±15% en ≥85/100); ADR-0016 agrega el criterio CP-01a-95 que es distinto.

## Tareas explícitas y trazabilidad

| Tarea | Ruta | Hito | Esfuerzo | Bloqueante CP-01a-95 |
|---|---|---|---:|:---:|
| H4-cal-1 — `factor_calibracion=0.85` | A | H4 | 2-3 h | Sí |
| H4-cal-2 — turn penalties en A* | A | H4 | 3-4 h | Sí |
| H4-cal-eval — verificar CP-01c | A | H4 | 1 h | Sí |
| H5-cal-3 — snap-to-edge | A | H5 | 6-8 h | Sí (ADR-0011 §V/L#5 lo exige) |
| H5-fix-1 — flags en `generate_osrm_fixture.py` | B | H5 | 1 h | Sí |
| H5-fix-2 — regenerar v3 (N≥300) | B | H5 | 1 h (con Docker) | Sí |
| H5-fix-3 — bootstrap/outliers sobre v3 | B | H5 | 0.5 h | Sí |
| H5-eval-95 — verificación final + accept ADR | A+B | H5 | 0.5 h | — |

**Total estimado**: 15-19 h distribuidas entre H4 y H5.

## Referencias

- [ADR-0011](0011-reformulacion-criterio-it01.md) §Verdad/Limitaciones #5 — la limitación que este ADR resuelve.
- [ADR-0013](0013-cp01c-criterio-calibrado.md) — Ruta A (mejoras 1 y 2) ya descompuesta; este ADR la promueve y agrega mejora 3.
- [ADR-0010](0010-routing-astar-y-validacion-osrm.md) — estrategia de validación OSRM oracle original.
- [`docs/quality/bootstrap-cp01a.md`](../../quality/bootstrap-cp01a.md) — punto de partida cuantitativo (IC95=[69,86], P=78.9%).
- [`docs/quality/outliers-sensibilidad.md`](../../quality/outliers-sensibilidad.md) — confirma que snap-to-node domina (68-77% de outliers) → snap-to-edge es la mejora con mayor impacto esperado.
- [`tools/bootstrap_cp01a.py`](../../../tools/bootstrap_cp01a.py) — herramienta de verificación del criterio.
- SRS sec. 2.13 — CP-01 fuente normativa, reformulada por ADR-0011, refinada por ADR-0013 (CP-01c) y este ADR (CP-01a-95).
