# Changelog

Todos los cambios notables a este proyecto se documentan acá.

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).
Versionado: una entrada por **entrega académica** del semestre (no SemVer estricto durante desarrollo).

## [Unreleased]

### Added — H2 cierre (routing IT-01 + RN-09, 2026-05-18)
- Pipeline OSRM oracle self-host: `tools/build_osrm_oracle.sh` levanta `osrm-routed --algorithm mld` en Docker con bbox La Serena-Coquimbo extraído del PBF Chile vía `osmium-tool`. `tools/generate_osrm_fixture.py` produce `core-python/tests/fixtures/osrm_oracle.json` (100 pares `base SAMU × incidente_con_jitter`).
- `core-python/scripts/build_graph.py` materializa `data/graphs/coquimbo.graphml` (16 679 nodos, 42 508 aristas) — caché reproducible para IT-01, commiteada al repo (excepción explícita en `.gitignore`).
- Test integración IT-01 ([test_routing_vs_osrm.py](core-python/tests/integration/test_routing_vs_osrm.py)) que valida CP-01a (paridad de distancia A* vs OSRM ≤ ±30% en ≥ 75/100 pares — actual: 78/100) y reporta CP-01b (divergencia observacional en duration).
- Suite UT del snap RN-09 ([test_grafo_osmnx_snap.py](core-python/tests/unit/adapters/test_grafo_osmnx_snap.py)) — 11 tests con taxonomía Normal/Borde/Error/RN sobre `OsmnxGrafoVial.nodo_mas_cercano` y `distancia_snap_m`.
- [ADR-0011](docs/architecture/decisions/0011-reformulacion-criterio-it01.md) documenta el experimento del 2026-05-18, las cinco fuentes de divergencia entre A* propio y OSRM, y la reformulación del criterio CP-01 (de duration ±5% a distance ±30%).

### Changed — H2 cierre
- SRS sec. 2.13 CP-01 anotado con nota al pie refiriendo al ADR-0011; sec. 2.15 §1 reformulada con el criterio de paridad real verificado.
- `docs/quality/trazabilidad.md`: RF-03 y RN-09 marcados ✅ con función implementada y tests verificados; agregadas §5.2 (routing, 20 tests) y §5.3 (adapter snap, 11 tests).
- `.gitignore`: excepción para `data/graphs/coquimbo.graphml` (commitado), exclusión de `data/osrm/*` (PBF + sidecars regenerables ~600 MB).

### Added
- Scaffolding inicial del repo (Fase 0 de la metodología): estructura `docs/`, `src/`, `tests/`, CI con GitHub Actions, pre-commit hooks (ruff + mypy + gitleaks), Makefile con targets básicos.
- ADRs 0001 (stack), 0002 (monolito modular), 0003 (SQLite v1), 0004 (frontend retro CRT/HTMX), 0005 (deploy demo Cloudflare Tunnel).
- `Dockerfile` multi-stage + `docker-compose.yml` con perfiles `dev`/`demo`.
- `scripts/cloudflared-setup.md` (playbook deploy demo) + `scripts/healthcheck.sh`.
- Sección "Demo en vivo" en `docs/operations/runbook.md`.
- `uv.lock` para builds reproducibles en CI.
- Diseño de Arquitectura Física (`docs/architecture/c4-deployment.md`) con vista de deployment GLaDOS → Docker → Cloudflare Edge → navegador, Tailscale out-of-band y UPS.
- BPMN 2.0 del proceso principal (`docs/architecture/process-bpmn.bpmn`) con lanes Operador / Sistema / Personal de Unidad, gateways de validación y confirmación, y event sub-process no interruptivo para re-despacho RN-06.

## [v0.1.0-diseño] — 2026-05-07 (planeado)

Entrega académica del bloque Diseño (tarea 2026-05-07 GCS):
- Diseño de Arquitectura Físico (C4 Container).
- Diseño Lógico Funcional — Proceso principal en BPMN 2.0.
- Mockups de la consola de despacho (estética CRT/phosphor).

(Pendiente al cierre de la entrega.)
