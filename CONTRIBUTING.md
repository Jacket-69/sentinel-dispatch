# Contribuir a Sentinel-Dispatch

> Proyecto académico cerrado al equipo (Benjamin + Fernando) durante el semestre 2026-S1. Tras el cierre, queda archivado en GitHub.

## Setup local

```bash
git clone git@github.com:Jacket-69/sentinel-dispatch.git
cd sentinel-dispatch
uv sync --all-groups
uv run pre-commit install
cp .env.example .env
make build-graph    # solo la primera vez (~2 min)
make db-init
make dev
```

## Flujo de trabajo

1. Toma una historia del [GitHub Project](https://github.com/users/Jacket-69/projects).
2. Crea rama desde `main`: `feat/<slug>`, `fix/<slug>`, `docs/<slug>`, etc.
3. Programa **con tests**.
4. `make ci` local antes del push.
5. Abre PR con título en [Conventional Commits](https://www.conventionalcommits.org/).
6. Espera CI verde + review aprobado + DoD cumplido (ver `docs/quality/definition-of-done.md`).
7. Merge + borrar rama remota.

## DoD checklist (resumen — ver `docs/quality/definition-of-done.md` para detalle)

- [ ] Cumple criterios de aceptación de la historia.
- [ ] Tests relevantes (unit en dominio, integración si toca BD/API).
- [ ] CI verde (lint, typecheck, tests).
- [ ] Review aprobado.
- [ ] Doc actualizada en el mismo PR si cambió comportamiento.
- [ ] Sin secretos commiteados.
- [ ] CHANGELOG actualizado si user-facing.

## Convenciones de código

Ver `docs/coding-standards.md` para el detalle. En resumen:

- **Lenguaje del dominio en el código** (ver glosario `docs/product/glossary.md`).
- **Tipos fuertes en magnitudes físicas** — distancias en metros, tiempos en segundos, velocidades en m/s. Conversión solo en el borde.
- **Logs con structlog**, eventos namespaced, nunca `print` en producción.
- **`ruff` y `mypy` estrictos** en módulos de dominio (`triaje`, `routing`, `dispatch`).

## Conventional Commits

```
feat(triaje): agregar árbol MPDS-subset con 7 preguntas
fix(astar): corregir heurística para puntos en isla sin conexión
docs(architecture): añadir ADR sobre persistencia
test(dispatch): cubrir caso CL-05 (re-despacho denegado por progreso)
```

Tipos válidos: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `perf`, `ci`, `revert`.

## ADRs

Si tomas una decisión que cumple **al menos una** de:

- Cambia cómo se construye/despliega/opera el sistema.
- Es costosa de revertir.
- Hubo más de una alternativa razonable.
- En 3 meses alguien podría preguntar "¿por qué hicimos esto así?".

→ escribe un ADR en `docs/architecture/decisions/NNNN-<slug>.md` siguiendo `0000-template.md`.

## Reportar un bug

Abre issue en GitHub con: descripción, pasos para reproducir, comportamiento esperado vs observado, versión, logs relevantes (sin datos sensibles).
