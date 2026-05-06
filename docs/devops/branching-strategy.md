# Branching strategy

**GitHub Flow** + **Conventional Commits**.

## Reglas

- `main` siempre desplegable.
- Una rama por historia/bugfix/doc.
- Ramas cortas (días, no semanas).
- PR antes del merge; review obligatoria; CI verde; DoD cumplido.
- Borrar rama remota tras el merge.

## Naming

- `feat/<slug>` — funcionalidad nueva
- `fix/<slug>` — bugfix
- `docs/<slug>` — solo doc
- `refactor/<slug>` — sin cambio de comportamiento
- `chore/<slug>` — tooling, deps, build
- `test/<slug>` — agregar/corregir tests
- `ci/<slug>` — pipeline

## Conventional Commits — tipos

`feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `perf`, `ci`, `revert`.

`BREAKING CHANGE:` en footer si rompe contrato público.

Validado en pre-commit (`commitizen`).
