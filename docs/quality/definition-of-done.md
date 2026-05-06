# Definition of Done

> Una tarea está **Done** si y solo si cumple **todos** los criterios. Si falta uno, no se mergea. Sin excepciones.

## Checklist canónico

- [ ] Cumple los **criterios de aceptación** declarados en la historia.
- [ ] Tiene **tests relevantes**:
  - Unit en lógica de dominio (`triaje`, `routing`, `dispatch`).
  - Integración si toca BD, API o adaptadores externos.
  - Test del dataset (`-m dataset`) si afecta el comportamiento sobre los 12 incidentes del SRS.
- [ ] **CI verde** — `make ci` (lint + typecheck + tests) pasa sin warnings nuevos.
- [ ] **Code review aprobado** por la otra persona del equipo antes de mergear.
- [ ] No rompe **lint ni typecheck** (`ruff` y `mypy`).
- [ ] **Documentación actualizada en el mismo PR** si cambió:
  - Comportamiento observable.
  - Contrato de API.
  - Esquema de BD (incluye migración Alembic).
  - Variables de entorno (`.env.example`).
  - Convenciones de código (`docs/coding-standards.md`).
  - Términos del dominio (`docs/product/glossary.md`).
- [ ] **No introduce secretos ni datos sensibles** (verificado por `gitleaks` en pre-commit + CI).
- [ ] **CHANGELOG.md** actualizado si la historia es user-facing o cambia comportamiento observable.
- [ ] **Logs estructurados** (`structlog`) para los eventos relevantes del cambio. Sin `print()` en producción.
- [ ] **Métricas y health checks** intactos o ampliados, no degradados.
- [ ] Si tomó una decisión costosa de revertir → **ADR nuevo** en `docs/architecture/decisions/`.

## "Funciona en mi máquina" no es Done

CI verde + review aprobada lo son. El estado del repo en `main` debe ser desplegable en cualquier momento.

## Excepciones documentadas

Si por una razón concreta una historia no puede cumplir un punto del DoD, se documenta en el PR como `**DoD desviación:**` con justificación. La desviación pasa por review explícita.

Ejemplos válidos de desviación:
- Spike de investigación que se mergea sin tests porque el código se va a borrar (debe estar marcado `# SPIKE — borrar tras decisión`).
- Hotfix de producción que se mergea con tests pendientes y un follow-up issue creado.

Ejemplos **inválidos**:
- "No tuve tiempo de escribir tests."
- "El typecheck era muy estricto."
- "La doc la actualizo después."
