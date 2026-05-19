#!/usr/bin/env bash
# ===========================================================================
# build_osrm_oracle.sh — Pipeline OSRM self-host para validar IT-01.
#
# Estrategia ADR-0010 §3: levantamos un OSRM offline con bbox Coquimbo,
# generamos el fixture una sola vez en local y lo committeamos al repo.
# CI nunca toca OSRM. Una vez que el fixture vive en
# tests/fixtures/osrm_oracle.json, este script solo se vuelve a correr si
# el grafo OSM cambia (al regenerar coquimbo.graphml) o si hace falta
# regenerar el fixture por otra razón documentada.
#
# Requisitos:
#   - docker daemon corriendo
#   - ~600 MB de disco libre (PBF Chile + datos OSRM preprocesados)
#   - ~1 GB RAM para osrm-extract/partition/customize
#
# Uso:
#   tools/build_osrm_oracle.sh [--skip-download]
#
# Resultado: container "sentinel-osrm" sirviendo /route/v1/driving en :5000.
# Cuando termines de generar el fixture, ejecuta:
#   docker stop sentinel-osrm && docker rm sentinel-osrm
# ===========================================================================

set -euo pipefail

# --- Configuración ---------------------------------------------------------
# Bbox La Serena-Coquimbo (mismo de adapters.grafo_osmnx.BBOX_IV_REGION).
BBOX_LEFT="-71.45"
BBOX_BOTTOM="-30.10"
BBOX_RIGHT="-71.15"
BBOX_TOP="-29.85"

PBF_URL="https://download.geofabrik.de/south-america/chile-latest.osm.pbf"
DATA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/data/osrm"
PBF_CHILE="${DATA_DIR}/chile-latest.osm.pbf"
PBF_BBOX="${DATA_DIR}/coquimbo.osm.pbf"
OSRM_BASENAME="coquimbo"
OSRM_PORT="${OSRM_PORT:-5000}"
OSRM_CONTAINER="${OSRM_CONTAINER:-sentinel-osrm}"

IMG_OSMIUM="iboates/osmium:latest"
IMG_OSRM="ghcr.io/project-osrm/osrm-backend:latest"

# --- Helpers ---------------------------------------------------------------
log() { printf "\033[36m[osrm-oracle]\033[0m %s\n" "$*"; }

skip_download=false
for arg in "$@"; do
    case "$arg" in
        --skip-download) skip_download=true ;;
        *) log "argumento desconocido: $arg"; exit 64 ;;
    esac
done

mkdir -p "${DATA_DIR}"

# --- 1. PBF Chile ----------------------------------------------------------
if [[ "${skip_download}" != "true" && ! -s "${PBF_CHILE}" ]]; then
    log "Descargando PBF Chile desde Geofabrik (~325 MB)…"
    curl -L --fail -o "${PBF_CHILE}" "${PBF_URL}"
else
    log "PBF Chile ya presente: ${PBF_CHILE} ($(du -h "${PBF_CHILE}" | cut -f1))"
fi

# --- 2. Extraer bbox Coquimbo con osmium -----------------------------------
if [[ ! -s "${PBF_BBOX}" ]]; then
    log "Recortando bbox Coquimbo (${BBOX_LEFT},${BBOX_BOTTOM},${BBOX_RIGHT},${BBOX_TOP})…"
    docker run --rm -v "${DATA_DIR}:/data" "${IMG_OSMIUM}" \
        extract \
        --bbox="${BBOX_LEFT},${BBOX_BOTTOM},${BBOX_RIGHT},${BBOX_TOP}" \
        --overwrite \
        -o "/data/$(basename "${PBF_BBOX}")" \
        "/data/$(basename "${PBF_CHILE}")"
else
    log "Bbox PBF ya presente: ${PBF_BBOX} ($(du -h "${PBF_BBOX}" | cut -f1))"
fi

# --- 3. Pipeline OSRM ------------------------------------------------------
# osrm-extract usa el perfil "car.lua" interno de la imagen. Genera
# coquimbo.osrm + sidecars en DATA_DIR.
if [[ ! -s "${DATA_DIR}/${OSRM_BASENAME}.osrm" ]]; then
    log "Ejecutando osrm-extract (perfil car.lua)…"
    docker run --rm -v "${DATA_DIR}:/data" "${IMG_OSRM}" \
        osrm-extract -p /opt/car.lua "/data/$(basename "${PBF_BBOX}")"
fi

# osrm-partition + osrm-customize: necesarios para el algoritmo MLD.
if [[ ! -s "${DATA_DIR}/${OSRM_BASENAME}.osrm.partition" ]]; then
    log "Ejecutando osrm-partition…"
    docker run --rm -v "${DATA_DIR}:/data" "${IMG_OSRM}" \
        osrm-partition "/data/${OSRM_BASENAME}.osrm"
fi

# El indicador de "customize hecho" es ``datasource_names``: lo genera
# customize, no partition (que sí genera ``.osrm.cells`` y ``.osrm.partition``).
if [[ ! -s "${DATA_DIR}/${OSRM_BASENAME}.osrm.datasource_names" ]]; then
    log "Ejecutando osrm-customize…"
    docker run --rm -v "${DATA_DIR}:/data" "${IMG_OSRM}" \
        osrm-customize "/data/${OSRM_BASENAME}.osrm"
fi

# --- 4. Levantar osrm-routed -----------------------------------------------
if docker ps -a --format '{{.Names}}' | grep -q "^${OSRM_CONTAINER}\$"; then
    log "Eliminando container previo ${OSRM_CONTAINER}…"
    docker rm -f "${OSRM_CONTAINER}" >/dev/null
fi

log "Levantando osrm-routed (MLD) en :${OSRM_PORT}…"
docker run -d \
    --name "${OSRM_CONTAINER}" \
    -p "${OSRM_PORT}:5000" \
    -v "${DATA_DIR}:/data" \
    "${IMG_OSRM}" \
    osrm-routed --algorithm mld "/data/${OSRM_BASENAME}.osrm" >/dev/null

# Espera activa (máx 30 s) a que /status responda 200.
log "Esperando OSRM en http://localhost:${OSRM_PORT}/…"
for _ in $(seq 1 30); do
    if curl -fsS "http://localhost:${OSRM_PORT}/nearest/v1/driving/-71.2535,-29.9077" >/dev/null 2>&1; then
        log "OSRM listo en http://localhost:${OSRM_PORT}/"
        log "Para detenerlo: docker stop ${OSRM_CONTAINER} && docker rm ${OSRM_CONTAINER}"
        exit 0
    fi
    sleep 1
done

log "ERROR: OSRM no respondió en 30 s. Logs:"
docker logs "${OSRM_CONTAINER}" | tail -20
exit 1
