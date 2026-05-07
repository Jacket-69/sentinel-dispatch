# Changelog

Todos los cambios notables a este proyecto se documentan acá.

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).
Versionado: una entrada por **entrega académica** del semestre (no SemVer estricto durante desarrollo).

## [Unreleased]

### Added
- Scaffolding inicial del repo (Fase 0 de la metodología): estructura `docs/`, `src/`, `tests/`, CI con GitHub Actions, pre-commit hooks (ruff + mypy + gitleaks), Makefile con targets básicos.
- ADRs 0001 (stack), 0002 (monolito modular), 0003 (SQLite v1), 0004 (frontend retro CRT/HTMX), 0005 (deploy demo Cloudflare Tunnel).
- `Dockerfile` multi-stage + `docker-compose.yml` con perfiles `dev`/`demo`.
- `scripts/cloudflared-setup.md` (playbook deploy demo) + `scripts/healthcheck.sh`.
- Sección "Demo en vivo" en `docs/operations/runbook.md`.
- `uv.lock` para builds reproducibles en CI.

## [v0.1.0-diseño] — 2026-05-07 (planeado)

Entrega académica del bloque Diseño (tarea 2026-05-07 GCS):
- Diseño de Arquitectura Físico (C4 Container).
- Diseño Lógico Funcional — Proceso principal en BPMN 2.0.
- Mockups de la consola de despacho (estética CRT/phosphor).

(Pendiente al cierre de la entrega.)
