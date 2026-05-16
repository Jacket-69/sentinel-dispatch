# Cloudflare Tunnel — setup para demo

> Playbook reproducible para exponer Sentinel-Dispatch corriendo en `GLaDOS` (PC casa) a internet, sin abrir puertos del router. Ver [ADR-0005](../docs/architecture/decisions/0005-deploy-demo.md) para la decisión.

## Dos modos

### Modo 1 — Quick Tunnel (efímero)

URL aleatoria `*.trycloudflare.com`, **sin cuenta Cloudflare**, ideal para probar antes de la defensa.

```bash
cd ~/Repositorios/sentinel-dispatch
docker compose --profile demo up -d

# Ver URL asignada (cambia en cada arranque del contenedor)
docker compose logs cloudflared | grep -E 'https://.*\.trycloudflare\.com'
```

Salida esperada:
```
2026-XX-XX ... INF +--------------------------------------------------------------------------------------------+
2026-XX-XX ... INF |  Your quick Tunnel has been created! Visit it at (it may take some time to be reachable):  |
2026-XX-XX ... INF |  https://random-words-here.trycloudflare.com                                               |
2026-XX-XX ... INF +--------------------------------------------------------------------------------------------+
```

Verificar:
```bash
curl -i https://random-words-here.trycloudflare.com/healthz
# → HTTP/2 200; {"status":"alive","version":"0.1.0"}
```

**Limitación:** la URL cambia en cada `docker compose restart cloudflared`. Sirve para pruebas, **no** para defensa con URL anticipada al profesor.

### Modo 2 — Named Tunnel (URL estable)

URL fija con dominio propio. Requiere cuenta Cloudflare gratis + dominio gestionado por Cloudflare DNS.

#### Setup único (una sola vez)

1. **Crear cuenta Cloudflare** (gratis): https://dash.cloudflare.com/sign-up
2. **Agregar dominio a Cloudflare** (mover NS al de Cloudflare; tarda ~24h una vez).
3. **Instalar `cloudflared` localmente** (no en Docker para este paso):
   ```bash
   # Arch/CachyOS
   yay -S cloudflared-bin
   # o descargar binario de https://github.com/cloudflare/cloudflared/releases
   ```
4. **Login**:
   ```bash
   cloudflared tunnel login
   # Abre browser, seleccionar dominio, autorizar.
   # Guarda credenciales en ~/.cloudflared/cert.pem
   ```
5. **Crear el túnel**:
   ```bash
   cloudflared tunnel create sentinel-dispatch
   # Devuelve UUID y crea ~/.cloudflared/<UUID>.json
   ```
6. **Configurar la ruta DNS**:
   ```bash
   cloudflared tunnel route dns sentinel-dispatch sentinel.tu-dominio.dev
   ```
7. **Obtener el token** para usarlo en Docker:
   ```bash
   # Dashboard: Zero Trust → Networks → Tunnels → sentinel-dispatch → Configure → Token
   # Copiar el string que empieza con "ey..."
   ```
8. **Agregar al `.env`**:
   ```bash
   echo "CLOUDFLARED_TOKEN=ey..." >> .env
   ```
9. **Editar `docker-compose.yml`** — reemplazar el `command:` del servicio `cloudflared` por:
   ```yaml
   command: tunnel --no-autoupdate run --token ${CLOUDFLARED_TOKEN}
   ```

#### Uso recurrente

```bash
docker compose --profile demo up -d
# Listo. https://sentinel.tu-dominio.dev resuelve siempre.
```

## Pre-flight checks (T = tiempo antes de la defensa)

### T-7 días (drill completo)

- [ ] Levantar tunnel y verificar URL responde desde **otra red** (datos móviles, no WiFi de casa).
- [ ] Ejecutar `curl https://<url>/healthz` 10 veces → todas 200 OK.
- [ ] Hacer una demo completa simulada (triaje + despacho + log) desde otra red.
- [ ] Anotar latencia promedio (debe ser <500 ms desde Chile).
- [ ] Documentar issues encontrados.

### T-24h

- [ ] Verificar que el PC tiene espacio en disco (>10 GB libres).
- [ ] `docker compose pull` para refrescar imagen `cloudflared`.
- [ ] `docker compose --profile demo up -d` y dejar corriendo.
- [ ] Confirmar UPS conectado (si lo tienes).
- [ ] Verificar que Tailscale está activo en el PC y en el celular.
- [ ] Test de reinicio remoto desde celular: `ssh glados 'docker compose restart app'`.

### T-2h

- [ ] Verificar `/healthz` y `/readyz` devuelven 200.
- [ ] Verificar URL pública responde.
- [ ] Confirmar screencast de respaldo en celular y Google Drive.

### T-30min

- [ ] Última verificación: cargar la URL pública y hacer un despacho de prueba con I-01.
- [ ] Dejar terminal de Tailscale abierta en el celular.

## Reinicio desde el celular durante la defensa

Si la app se cuelga:

```bash
# Desde Termux + ssh:
ssh glados
cd ~/Repositorios/sentinel-dispatch
docker compose restart app
docker compose ps
```

Si el tunnel pierde conexión:

```bash
ssh glados
cd ~/Repositorios/sentinel-dispatch
docker compose restart cloudflared
docker compose logs --tail=20 cloudflared
```

Si todo está roto y no se recupera en <2 min: **abrir el screencast en el proyector y narrar**.

## Healthcheck cron (mitigación 5)

Crear `/usr/local/bin/sentinel-healthcheck.sh`:

```bash
#!/usr/bin/env bash
# Verifica que la app responde; reinicia si no.
set -e
URL="${SENTINEL_URL:-http://localhost:8000/healthz}"
COMPOSE_DIR="${SENTINEL_COMPOSE_DIR:-/home/jacket/Repositorios/sentinel-dispatch}"

if ! curl -fsS --max-time 5 "$URL" > /dev/null; then
  logger -t sentinel-healthcheck "FAILED: $URL — restarting app"
  cd "$COMPOSE_DIR" && docker compose restart app
fi
```

Cron entry (`crontab -e`):

```cron
*/5 * * * * /usr/local/bin/sentinel-healthcheck.sh
```

Activar solo en los días previos a la defensa; desactivar después.

## Troubleshooting

| Problema | Causa probable | Acción |
|---|---|---|
| `cloudflared` reinicia constantemente | `app` no está healthy | `docker compose logs app` — revisar errores de arranque |
| URL responde 502 | App vivo pero `/healthz` falla en Docker | Verificar `curl http://localhost:8000/healthz` desde host |
| URL responde 404 | Tunnel apunta a path equivocado | Revisar `command:` en docker-compose.yml |
| Token rechazado | Token expirado o de otro tunnel | Regenerar en Dashboard → Networks → Tunnels |
| Latencia alta (>2 s) | ISP limitando UDP o ruta sub-óptima | Cambiar a `--protocol http2` en el command |

## Referencias

- Cloudflare Tunnel docs: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/
- Quick tunnels: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/do-more-with-tunnels/trycloudflare/
- Tailscale (mitigación de acceso remoto): https://tailscale.com/kb/1017/install
