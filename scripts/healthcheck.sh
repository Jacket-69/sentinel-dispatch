#!/usr/bin/env bash
# Healthcheck para cron — reinicia el servicio app si /healthz falla.
# Activar 1 semana antes de la defensa, desactivar después.
#
# Instalar:
#   sudo cp scripts/healthcheck.sh /usr/local/bin/sentinel-healthcheck.sh
#   sudo chmod +x /usr/local/bin/sentinel-healthcheck.sh
#
# Cron (crontab -e):
#   */5 * * * * /usr/local/bin/sentinel-healthcheck.sh

set -euo pipefail

URL="${SENTINEL_URL:-http://localhost:8000/healthz}"
COMPOSE_DIR="${SENTINEL_COMPOSE_DIR:-/home/jacket/Repositorios/sentinel-dispatch}"
TIMEOUT="${SENTINEL_TIMEOUT:-5}"

if ! curl -fsS --max-time "$TIMEOUT" "$URL" > /dev/null; then
  logger -t sentinel-healthcheck "FAILED: $URL — restarting app"
  cd "$COMPOSE_DIR" && docker compose restart app
  exit 1
fi

exit 0
