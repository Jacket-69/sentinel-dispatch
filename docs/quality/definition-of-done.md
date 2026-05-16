# Definition of Done

> Una tarea está **Done** si y solo si cumple **todos** los criterios bloqueantes. Si falta uno, no se mergea.
>
> **Versión académica recortada — Sentinel-Dispatch v1**. Proporcional a equipo de 2 personas / horizonte de 2 meses. El frame industrial completo (con code review obligatorio, CHANGELOG por PR, métricas DORA medidas) es opt-in y queda fuera de este DoD por decisión consciente — ver `Planificación/Metodología aplicada.md` del vault y `Plan B - Reestructuración.md`.

## Criterios bloqueantes

Sin estos cumplidos, el PR no mergea:

- [ ] Cumple los **criterios de aceptación** declarados en la historia o issue.
- [ ] **Tests unit** en la lógica de dominio nueva (`core-python/.../domain/{triaje,routing,dispatch}/`). Si tocaste solo adapter o interfaz: tests de integración acotados.
- [ ] **CI verde** — `make ci` pasa sin warnings nuevos. Esto incluye:
  - `ruff check` + `ruff format --check` (Python)
  - `mypy strict` en `domain/`, `application/`, `ports/`
  - `pytest -m "not dataset and not slow"`
  - `mvn verify` (cuando exista `core-java/` con código)
- [ ] **No introduce secretos** (gitleaks en pre-commit + CI).
- [ ] Si cambió **comportamiento observable** o **contrato** (API, formato del log, schema del dataset): **doc actualizada en el mismo PR**.
- [ ] Si tomó una **decisión costosa de revertir** (cambio de stack, de patrón arquitectónico, de estrategia de despliegue): **ADR nuevo** en `docs/architecture/decisions/NNNN-<slug>.md`.

## Prácticas recomendadas (no bloqueantes)

Se aplican cuando aplican; no frenan el merge:

- **Code review por par**: si Fernando o el SQA Lead están disponibles, revisar antes de merge. Si no, auto-revisión documentada en la descripción del PR.
- **Logs estructurados** con `structlog` para eventos nuevos del dominio. Eventos namespaced (`triaje.*`, `dispatch.*`, `astar.*`).
- **CHANGELOG**: se actualiza una vez por **entrega académica** (Segunda Evaluación, Avance 2, Final), no por PR.
- **Métricas y health checks**: si el cambio toca observabilidad, mantenerla o ampliarla. Si no, no degradar lo existente.

## "Funciona en mi máquina" no es Done

CI verde + criterios de aceptación cumplidos lo son. El estado del repo en `main` debe ser ejecutable en cualquier momento.

## Excepciones documentadas

Si una historia no puede cumplir un criterio bloqueante por razón concreta, se documenta en el PR como `**DoD desviación:**` con justificación. La desviación queda registrada en `docs/quality/dod-deviations.md` (creado al primer uso) con fecha, PR, criterio omitido, razón y plan de remediación.

Ejemplos **válidos** de desviación:

- Spike de investigación que se mergea sin tests porque el código se va a borrar (marcado con `# SPIKE — borrar tras decisión`).
- Hotfix justo antes de entrega académica con tests pendientes y follow-up issue creado.

Ejemplos **inválidos** (rechazar):

- "No tuve tiempo de escribir tests."
- "El typecheck era muy estricto."
- "La doc la actualizo después."

## Cumplimiento RT (transversal a todo PR que toque el núcleo de cálculo)

Si el PR modifica triaje, routing o dispatch en `core-python/.../domain/`:

- [ ] Si la modificación cambia el comportamiento sobre el dataset, ejecutar `make compare` localmente y revisar el reporte de equivalencia (cuando `core-java/` tenga implementación, post-H3).
- [ ] Si la diferencia con `core-java/` excede la tolerancia configurada (ver ADR-0008), abrir issue de seguimiento o ajustar la implementación.

Esto es **bloqueante post-H3** (cuando ambos cores tengan implementación). Antes de H3 no aplica.

## Referencias

- `docs/quality/sqa-plan.md` — Plan SQA del proyecto.
- `docs/quality/testing-strategy.md` — Pirámide de testing.
- `docs/architecture/decisions/0008-validacion-dual-java-python.md` — Mecanismo RT.
- `Recursos/Procesos/Metodología de Proyectos/Calidad y DoD.md` (vault) — DoD canónico industrial (versión completa, no aplicada acá por contexto académico).
