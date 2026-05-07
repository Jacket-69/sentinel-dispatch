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

## Demo en vivo (defensa académica)

Stack confirmado en [ADR-0005](../architecture/decisions/0005-deploy-demo.md): Cloudflare Tunnel desde `GLaDOS` (PC casa) + mitigaciones de resiliencia. Playbook detallado en [`scripts/cloudflared-setup.md`](../../scripts/cloudflared-setup.md).

### Pre-flight

| Cuándo | Qué |
|---|---|
| **T-7 días** | Drill completo: levantar tunnel, verificar URL desde otra red, demo simulada con datos móviles, anotar latencia |
| **T-24 h** | Pull imagen `cloudflared`, levantar `docker compose --profile demo up -d`, confirmar UPS, Tailscale activo en PC y celular, test de reinicio remoto |
| **T-2 h** | `/healthz` y `/readyz` 200, URL pública responde, screencast de respaldo confirmado en celular + Drive |
| **T-30 min** | Última verificación con un despacho de prueba sobre I-01 |

### Reinicio remoto desde celular durante la defensa

```bash
# Desde Termux + ssh (Tailscale):
ssh glados
cd ~/Documentos/Repositorios/UNIVERSIDAD/sentinel-dispatch
docker compose restart app          # si la app se cuelga
docker compose restart cloudflared  # si el tunnel pierde conexión
```

Si todo está roto y no se recupera en <2 min: **abrir el screencast en el proyector y narrar**.

### Healthcheck cron (mitigación 5)

```bash
sudo cp scripts/healthcheck.sh /usr/local/bin/sentinel-healthcheck.sh
sudo chmod +x /usr/local/bin/sentinel-healthcheck.sh
# crontab -e:
# */5 * * * * /usr/local/bin/sentinel-healthcheck.sh
```

Activar 1 semana antes de la defensa, desactivar después.

## Rollback (deploy demo)

1. Identificar el último tag estable: `git tag -l 'v*' | tail -3`.
2. Re-deploy: `git checkout <tag> && docker compose --profile demo up -d --build`.
3. Verificar `/healthz` y ejecutar despacho de prueba sobre I-01.
4. Si el rollback no resuelve, abrir screencast pre-grabado.

## Reconstruir grafo OSM

```bash
make build-graph    # ~2 min
```

Si OSM cambia significativamente la red de la región, regenerar y commitear nuevo hash en `data/graphs/.version`.
