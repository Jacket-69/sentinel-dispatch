# Sentinel-Dispatch

> Motor de despacho eficiente para unidades de emergencia médica — IV Región de Coquimbo, Chile.

Reformulación rigurosa de propuesta original Cornejo-Michea con triaje clínico (MPDS-subset),
ruteo A* sobre grafo OSM real, y función de despacho multiobjetivo justificada.
Proyecto académico del ramo **Gestión de Calidad del Software** (UCEN, 2026-S1, Prof. Gonzalo Honores).

> ⚠️ **Subset inspirado en MPDS**, no protocolo certificado. No usar en sistemas de salud reales sin certificación clínica (R-08).

## Documentación

- [Visión](docs/product/vision.md)
- [Requisitos (SRS vivo)](docs/requirements/requirements.md)
- [Arquitectura — overview](docs/architecture/overview.md)
- [C4 Context](docs/architecture/c4-context.md) · [C4 Container](docs/architecture/c4-container.md)
- [BPMN proceso principal](docs/architecture/process-bpmn.md)
- [API OpenAPI](docs/api/openapi.yaml)
- [Modelo de datos](docs/database/model.md)
- [Definition of Done](docs/quality/definition-of-done.md)
- [Estrategia de testing](docs/quality/testing-strategy.md)
- [Runbook](docs/operations/runbook.md)
- [ADRs](docs/architecture/decisions/)

## Estado

- **Versión:** v0.1.0-dev
- **Fase:** F0 (Preparación) → F2 (Diseño técnico)
- **Entorno:** local
- **Próxima entrega académica:** 2026-05-07 — bloque Diseño (Arq Física + BPMN + Mockups)


- Benjamín López
- Fernando Godoy M.

## Licencia

[MIT](LICENSE)
