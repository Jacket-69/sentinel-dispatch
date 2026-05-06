# Runbook — Sentinel-Dispatch

> Versión académica (corta). Aplica a deploy local + demo.

## Health checks

- `GET /healthz` → `{"status":"alive"}` si proceso vivo.
- `GET /readyz` → `{"status":"ready"}` si BD conectada y grafo cargado.

## Síntomas → acciones

| Síntoma | Diagnóstico | Acción |
|---|---|---|
| `/readyz` devuelve 503 | Logs: ¿"graph load failed"? | `make build-graph` y reiniciar |
| Despacho tarda >1 s para flota chica | Logs: ¿`astar.duration` alto? | Verificar grafo cargado en RAM, no recomputándose |
| Error "DB locked" | SQLite con concurrencia rara | Reiniciar; si persiste, revisar transacciones largas |
| `make ci` falla en lint | `ruff` strict | `make format` aplica fixes |

## Backups

Diarios automáticos a `~/backups/sentinel-dispatch/sentinel-YYYYMMDD.db`. Restauración:

```bash
cp ~/backups/sentinel-dispatch/sentinel-YYYYMMDD.db data/sentinel.db
```

## Rollback (deploy demo)

Pendiente decisión ADR-0005. Esquema esperado:

1. Identificar tag/commit del último estado verde.
2. Re-deploy de ese tag.
3. Verificar `/healthz` y un despacho de prueba sobre I-01.

## Reconstruir grafo OSM

```bash
make build-graph    # ~2 min
```

Si OSM cambia significativamente la red de la región, regenerar y commitear nuevo hash en `data/graphs/.version`.
