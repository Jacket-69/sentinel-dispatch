# CI/CD

> Pipeline en `.github/workflows/ci.yml`.

## Etapas

```
1. lint        (ruff check + format check)
2. typecheck   (mypy)
3. test        (pytest sin dataset/slow)
4. security    (gitleaks)
```

Test corre solo si lint y typecheck pasan. Falla cualquiera → cierra el PR.

## Reglas

- **CI corre en cada push y cada PR a `main`.**
- **`main` protegido**: requiere PR + review + CI verde para mergear.
- **Cache** de uv habilitado.
- **Sin pasos manuales escondidos.**

## Local — reproducir CI

```bash
make ci
```

## Cuándo agregar etapas

- **Deploy automático** → cuando se decida ADR-0005 (deploy demo).
- **Tests del dataset** → opcional en CI (lentos); por ahora solo local con `make test-dataset`.
- **Build de Docker image** → cuando llegue el deploy.
