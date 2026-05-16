# DevOps — branching, commits y CI/CD

> Convenciones de Git y pipeline de CI. Consolida lo que antes estaba en `devops/branching-strategy.md` y `devops/ci-cd.md`.

## Branching — GitHub Flow

- `main` siempre desplegable.
- Una rama por historia / bugfix / doc.
- Ramas cortas (días, no semanas).
- PR antes del merge; review obligatoria; CI verde; DoD cumplido.
- Borrar rama remota tras el merge.

### Naming

| Prefijo | Uso |
|---|---|
| `feat/<slug>` | Funcionalidad nueva |
| `fix/<slug>` | Bugfix |
| `docs/<slug>` | Solo doc |
| `refactor/<slug>` | Sin cambio de comportamiento |
| `chore/<slug>` | Tooling, deps, build |
| `test/<slug>` | Agregar/corregir tests |
| `ci/<slug>` | Pipeline |

## Conventional Commits

Tipos aceptados: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `perf`, `ci`, `revert`.

`BREAKING CHANGE:` en footer si rompe contrato público.

Validado en pre-commit (`commitizen`).

## CI/CD

Pipeline en `.github/workflows/ci.yml`. Matriz dual desde H0 (Python + Java) por ADR-0008.

### Etapas

```
1. lint        (ruff check + format check ; spotless en Java)
2. typecheck   (mypy)
3. test        (pytest sin dataset/slow ; JUnit 5 en core-java)
4. security    (gitleaks)
5. dataset     (depende de test) — ejecuta los 12 incidentes en ambos cores
6. compare     (depende de dataset) — tools/compare_outputs.py — RT-02
7. report      (solo en push a main) — publica rt-validation-report.md
```

Test corre solo si lint y typecheck pasan. Falla cualquiera → cierra el PR.

### Reglas

- **CI corre en cada push y cada PR a `main`.**
- **`main` protegido**: requiere PR + review + CI verde para mergear.
- **Cache** de uv y de Maven habilitado.
- **Sin pasos manuales escondidos.**

### Local — reproducir CI

```bash
make ci              # pipeline completo
make test-python     # solo Python
make test-java       # solo Java
make test-dataset    # los 12 incidentes en ambos cores
make compare         # RT-02 comparación dual
```

### Cuándo agregar etapas

- **Deploy automático** → cuando se re-active ADR-0005 (deploy demo) — actualmente diferido a F4.
- **Tests del dataset en cada PR** → si se vuelven baratos. Hoy: solo en push a main + local.
- **Build de Docker image** → cuando llegue el deploy.
