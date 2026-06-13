# Fixtures de validación dual RT-02

Outputs reales de ambos núcleos sobre el dataset de aceptación del SRS
(sec. 2.12, 12 incidentes), commiteados como fixtures para la vista
`GET /consola/validacion` de la consola web. Un `*.jsonl` por incidente
(schema congelado en ADR-0017), separados por núcleo:

```
data/validacion/
├── python/   ← core-python (referencia)
└── java/     ← core-java (validación dual, ADR-0008)
```

## Procedencia

- **Fecha de generación:** 2026-06-12
- **Commit base:** `f9f81fb` (main)
- **Grafo:** `data/graphs/coquimbo.graphml` (16 679 nodos, 42 508 aristas)
- **Dataset:** `data/dataset/incidentes.json` + `data/dataset/unidades.json`

Comandos exactos (la misma sintaxis del job `compare` del CI):

```bash
# core-python (desde core-python/)
uv run sentinel run-dataset --out /tmp/python-out/

# core-java (desde core-java/)
mvn -B compile exec:java -Dexec.mainClass="cl.ucen.sentinel.cli.Main" \
  -Dexec.args="run-dataset --in ../data/dataset/incidentes.json --unidades ../data/dataset/unidades.json --graph ../data/graphs/coquimbo.graphml --out /tmp/java-out/"

# verificación con el comparador canónico
uv run --no-project python tools/compare_outputs.py \
  --python /tmp/python-out/ --java /tmp/java-out/ --report /tmp/rt-report.md
# → Comparados: 12 | OK: 12 | WARN: 0 | FAIL: 0 | MISSING: 0 | EXTRA: 0
```

## Vigencia

Estas fixtures son una foto de la paridad al commit base. El job `compare`
del CI (`.github/workflows/ci.yml`) ejecuta exactamente la misma validación
sobre los outputs frescos de ambos núcleos en cada PR; si el dominio cambia,
regenerar estas fixtures con los comandos de arriba en el mismo PR.
