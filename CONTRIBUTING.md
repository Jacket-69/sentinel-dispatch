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

## Spike-before-CP — convención del equipo

> Lección retroactiva del incidente CP-01 (ADR-0011): el criterio
> `|Δ_duration|/T_OSRM ≤ 0.05` se redactó en el SRS sin correr el
> experimento ni revisar literatura, y resultó **inalcanzable** con el
> A* simple del SRS. La corrección costó ADR-0011 completo + reformulación
> CP-01a + 22 outliers descompuestos. Para que no vuelva a pasar:

**Antes de aceptar un Caso de Prueba (CP) nuevo en el SRS, el equipo debe
ejecutar un *spike* empírico de viabilidad:**

1. Implementación mínima (puede ser ad-hoc en `tools/` o un cuaderno) que
   produzca el estadístico del CP sobre datos reales o un subset
   representativo.
2. Verificar que el criterio es **alcanzable** con la arquitectura
   propuesta — no por intuición, por número medido.
3. Documentar el resultado del spike en el ADR que introduce el CP, en
   una sección **Spike de viabilidad** con: dataset usado, métrica
   obtenida, decisión (aceptar / ajustar criterio / rechazar).
4. Si el spike revela que el criterio original no es alcanzable, **se
   ajusta antes** de entrar al SRS, no después (ADR-0011 es el contraejemplo
   de qué pasa si se invierte el orden).

CPs pendientes que requieren spike retroactivo antes de H4 (ADR-0011
§V/L#1):

- **CP-08** — *intento de edición del log JSONL*: spike = abrir un JSONL
  ya escrito, intentar editarlo, verificar que el adapter detecta la
  mutación. Si la detección depende de hashes/checksums fuera del scope
  del SRS, ajustar CP-08 antes de aceptarlo en H4.
- **CP-12** — *performance 50 unidades ≤ 1000 ms*: spike = generar
  dataset sintético de 50 unidades, correr el orquestador, medir
  wall-clock. Si la métrica está fuera del orden de magnitud, ajustar
  CP-12 (p. ej., a ≤ 2000 ms o reducir N) antes de aceptarlo.

Ambos spikes son responsabilidad del PR que abra H4 y deben aparecer en
ADRs subsecuentes (0016+) como sección "Spike de viabilidad".

## Reportar un bug

Abre issue en GitHub con: descripción, pasos para reproducir, comportamiento esperado vs observado, versión, logs relevantes (sin datos sensibles).
