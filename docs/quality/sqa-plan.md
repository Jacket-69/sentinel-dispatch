# Plan SQA — Sentinel-Dispatch

> **Estado:** placeholder.

## Objetivo

Asegurar calidad **durante todo el proceso**, no como checkpoint final.

## Prácticas por fase

- **F0 — Preparación:** CI con lint+test desde el primer commit; pre-commit hooks.
- **F1 — Descubrimiento:** criterios de aceptación claros (Given-When-Then) por historia.
- **F2 — Diseño:** trazabilidad RF→Historia→Test; ADRs por decisión costosa.
- **F3 — Desarrollo:** TDD donde aplique; review obligatoria; doc en mismo PR.
- **F4 — Release:** smoke tests post-deploy; rollback ensayado.
- **F5 — Mejora:** revisión de bugs y deuda técnica.

Ver detalle en `Recursos/Procesos/Metodología de Proyectos/Calidad y DoD.md` del vault.
