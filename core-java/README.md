# core-java — Núcleo de cálculo en Java

> Implementación dual del núcleo de Sentinel-Dispatch para cumplir el Requisito Transversal RT-01..RT-04 del SRS (Java vs Python). Decisión completa en [ADR-0008](../docs/architecture/decisions/0008-validacion-dual-java-python.md).

## Alcance

Solo el **núcleo de cálculo**: triaje MPDS-subset + A* sobre GraphML + función de costo. No tiene API, no tiene persistencia, no implementa re-despacho. Es una "simulación" del núcleo según el texto del profesor (RT-01: *implementado o simulado*).

## Cómo correr

Pre-requisito: Java 21 LTS + Maven instalados. Lee el grafo y el dataset ya versionados en `data/` (no genera nada ni accede a red).

```bash
# Desde core-java/
mvn clean test            # build + tests JUnit 5
mvn spotless:check        # formato
mvn spotless:apply        # aplicar formato
```

Ejecutar `run-dataset` (despacha sobre el dataset y emite un JSONL por incidente, insumo de la validación dual RT-02):

```bash
mvn exec:java -Dexec.mainClass="cl.ucen.sentinel.cli.Main" \
    -Dexec.args="run-dataset --in ../data/dataset/incidentes.json \
                              --graph ../data/graphs/coquimbo.graphml \
                              --out /tmp/java-out/"
```

> Más simple: desde la raíz del monorepo, `make test-dataset` corre el `run-dataset` de ambos cores y `make compare` verifica la paridad bit-exacta.

## Estructura

```
core-java/
├── pom.xml                        # Maven, Java 21, JGraphT, Jackson, JUnit 5, Spotless, JaCoCo
├── src/main/java/cl/ucen/sentinel/
│   ├── triaje/                    # Árbol MPDS-subset
│   ├── routing/                   # A* sobre grafo cargado de GraphML (JGraphT)
│   ├── dispatch/                  # Función de costo + argmin
│   ├── graph/                     # Cargador GraphML
│   └── cli/                       # Entry point (picocli)
└── src/test/java/cl/ucen/sentinel/ # JUnit 5 + AssertJ
```

## Estado

Núcleo implementado (H3-J ✓): triaje MPDS-subset + A\* sobre GraphML + función de costo, con suite JUnit 5 verde y validación dual **RT-02 12/12 bit-exacto** contra `core-python`. Estado y roadmap vivos en el README raíz del repo y en el vault del proyecto.

## Cumplimiento RT

| RT | Cómo lo cumple este módulo |
|---|---|
| RT-01 | Implementa el núcleo de cálculo (triaje + A* + costo) en Java |
| RT-02 | Genera outputs JSON con la misma estructura que `core-python`, comparados por `tools/compare_outputs.py` con tolerancia configurable |
| RT-03 | Diferencias se documentan automáticamente en `docs/quality/rt-validation-report.md` (generado en CI) |
| RT-04 | Justificación final en `docs/quality/rt-justification.md` al cierre del proyecto (H5) |

## Decisiones clave (ver ADR-0008)

- Lee el **mismo** `data/graphs/coquimbo.graphml` que produce `core-python` con OSMnx. Java no parsea OSM crudo.
- Lee el **mismo** dataset `data/dataset/incidentes.json`.
- Output JSON con el mismo schema que `core-python`.
- Sin acceso a red ni BD; solo filesystem.
