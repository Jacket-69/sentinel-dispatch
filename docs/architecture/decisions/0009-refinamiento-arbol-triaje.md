---
adr: 0009
title: Refinamiento del árbol MPDS-subset — variables categóricas y mapeo con MPDS oficial
status: accepted
date: 2026-05-15
deciders: Benjamin López
tags: [adr, dominio, triaje, mpds]
---

# ADR 0009 — Refinamiento del árbol MPDS-subset

## Contexto

La versión original del árbol de triaje en el SRS sec. 2.6-A (entregada 2026-04-30) usaba variables booleanas simples (`sangrado_activo`, `dolor_toracico`, `dificultad_resp`) y 7 reglas. Al implementar el esqueleto del módulo `domain/triaje/` el 2026-05-15 aparecieron **tres inconsistencias internas** entre el árbol del SRS y el dataset de aceptación sec. 2.12:

1. **Gradiente de dolor torácico**: el árbol trataba "dolor torácico" como booleano simple (`Sí` → Delta), pero el dataset distingue I-06 ("dolor torácico severo" → Charlie) e I-08 ("dolor torácico severo incapacitante" → Delta). El árbol no podía generar ambas categorías con la misma variable.
2. **Bravo pediátrico vs sangrado leve**: la regla original Bravo exigía "consciente=Sí ∧ grupo_etario=Pediátrico ∧ síntoma moderado", pero el dataset (I-02, I-03) clasifica Bravo con sangrado leve en adulto/anciano, no pediátrico.
3. **Falta de gradiente en sec 2.5**: las entradas del operador se definieron como booleanas puras, sin capturar los niveles que aparecen en el dataset ("sangrado leve" vs "activo" vs "peligroso"; "dolor torácico" vs "severo" vs "severo incapacitante").

Adicionalmente, las decisiones eran ad-hoc y no se contrastaban con MPDS oficial. La revisión de la literatura MPDS (Wikipedia 2026, IAED Journal, plantilla SAMU MINSAL 2018) confirmó que MPDS real opera con 36 Chief Complaints y subdeterminantes específicos por protocolo, no con un árbol único de booleanos.

## Decisión

Refinar el árbol de triaje del SRS-subset con tres cambios coordinados, manteniendo la propuesta como "subset inspirado en MPDS" (sin certificación, R-08 del SRS):

### 1. Variables de entrada con tipos categóricos

Reemplazar las booleanas planas de sec 2.5 por enums alineados a la granularidad MPDS:

| Variable | Tipo | Valores | Mapeo MPDS |
|---|---|---|---|
| `consciente` | bool | Sí, No | Pre-pregunta de Protocol 31 |
| `respira_normal` | bool | Sí, No | Distingue 31-D-2 vs 31-E-1 / 9-E-1 |
| `sangrado` | `NivelSangrado` | `NINGUNO`, `MODERADO`, `ACTIVO`, `PELIGROSO` | Protocol 21: (no aplica) / 21-B-2 / [adaptación] / 21-D-4 |
| `dolor_toracico` | `NivelDolorToracico` | `NINGUNO`, `PRESENTE`, `CRITICO` | Protocol 10: (no aplica) / 10-C / 10-D |
| `dificultad_respiratoria` | bool | Sí, No | Protocol 6 / Protocol 31-C-1 |
| `grupo_etario` | `GrupoEtario` | Pediátrico, Adulto, Anciano | Reservado para subdeterminantes futuros |

### 2. Árbol de 9 reglas en orden estricto

```text
1. consciente=No ∧ respira_normal=No                  → Echo     (9-E-1 / 31-E-1)
2. consciente=No ∧ respira_normal=Sí                  → Delta    (31-D-2)
3. consciente=Sí ∧ sangrado=PELIGROSO                 → Delta    (21-D-4)
4. consciente=Sí ∧ dolor_toracico=CRITICO             → Delta    (10-D)
5. consciente=Sí ∧ dolor_toracico=PRESENTE            → Charlie  (10-C)
6. consciente=Sí ∧ dificultad_respiratoria=Sí         → Charlie  (31-C-1 / 6-C)
7. consciente=Sí ∧ sangrado=ACTIVO                    → Charlie  (adaptación SAMU)
8. consciente=Sí ∧ sangrado=MODERADO                  → Bravo    (21-B-2)
9. consciente=Sí ∧ (resto)                            → Alpha    (sin Chief Complaint)
```

Verificación contra los 12 incidentes del dataset (sec. 2.12): cobertura 12/12 con clasificación exacta y determinista.

### 3. Renombre del dataset al vocabulario refinado

- "sangrado leve" del dataset original → `sangrado=MODERADO` (alineado a 21-B-2 Serious hemorrhage).
- "dolor torácico severo" → `dolor_toracico=PRESENTE` (alineado a 10-C).
- "dolor torácico severo incapacitante" → `dolor_toracico=CRITICO` (alineado a 10-D).

### 4. Eliminación de la regla "Bravo pediátrico + síntoma moderado"

La regla original era especulativa y no se valida con el dataset (los Bravo del dataset son adulto/anciano, no pediátrico). Se elimina; `grupo_etario` queda en el modelo de datos para subdeterminantes específicos futuros (ej. Protocol 6-D-1P) pero **no entra al árbol v1**.

## Alternativas consideradas

### A) Mantener el árbol booleano original y cambiar el dataset

- **Pros:** menos cambios al código y al SRS.
- **Contras:** rompe los casos de prueba académicos del dataset (sec. 2.12) que ya están entregados. Pierde fidelidad clínica.
- **Por qué se descarta:** el dataset fue construido pensando en gradientes reales; modificarlo para que case con un árbol simplista es perder calidad académica.

### B) Refinar solo con enums sin alinear con MPDS

- **Pros:** menos investigación.
- **Contras:** pierde defensa académica. El profesor pregunta explícitamente por el patrón MPDS y la pauta del ramo evalúa "justificación de decisiones".
- **Por qué se descarta:** la fundamentación MPDS es trabajo barato (búsquedas web + cita) y eleva mucho la calidad de la entrega.

### C) Modelar los 36 Chief Complaints de MPDS oficial

- **Pros:** fidelidad total al estándar.
- **Contras:** 36 protocolos × determinantes específicos = explosión de complejidad para 2 personas / 2 meses. Va contra R-08 (subset no certificado).
- **Por qué se descarta:** YAGNI fuerte. El subset cubre los 12 incidentes del dataset y se defiende como adaptación documentada.

### D) Agregar campo "ubicación del sangrado" para resolver I-04 con MPDS literal

- **Pros:** Charlie de I-04 sería MPDS literal (21-D-4 si está en zona peligrosa o 21-B-2 si no).
- **Contras:** carga adicional al operador (campo nuevo). El dataset original no lo tiene.
- **Por qué se descarta:** se prefiere la adaptación documentada (Regla 7) que es más simple operativamente y se justifica en el contexto SAMU Chile.

## Consecuencias

### Positivas

- **Cobertura exacta del dataset**: las 9 reglas clasifican los 12 incidentes sin ambigüedad ni discrepancia.
- **Defensa académica fuerte**: cada regla cita un determinante MPDS oficial; las decisiones son trazables.
- **Tests UT triviales**: cada regla es un caso de prueba unitario directo (UT por regla = 9 tests mínimos).
- **Adaptación SAMU explícita**: la regla 7 (sangrado activo → Charlie) se documenta como decisión consciente alineada al modelo de 5 niveles del MINSAL Chile, en lugar de ser un "bug del SRS".
- **Modelo extensible**: si en el futuro se agregan Chief Complaints específicos (ej. Protocol 6 pediátrico), el campo `grupo_etario` ya está reservado y los enums son extensibles sin breaking changes.

### Negativas / costo

- **Cambio al SRS LaTeX entregado**: requiere regenerar el `.pdf` y commitear nueva versión. Costo: ~5 minutos de compilación.
- **Refactor del esqueleto del triaje creado en H0**: los `tipos.py` y `arbol.py` se reescriben (afortunadamente sin tests aún en H0, así que no se rompe nada).
- **Mayor número de variables**: 6 inputs en lugar de 4. El formulario del operador es ligeramente más largo (compensado por menos ambigüedad).

### Neutras

- `grupo_etario` queda como variable retenida sin uso en el árbol v1. Si nunca se usa, se puede deprecar más adelante (no urge).

## Cumplimiento / verificación

- **SRS sec. 2.5** actualizada con variables enum y mapeo MPDS explícito.
- **SRS sec. 2.6-A** reescrita con las 9 reglas y nueva subsección **A.1 Mapeo con MPDS oficial** (tabla regla → determinante).
- **SRS sec. 2.12** (dataset) actualizada con vocabulario refinado y cita de regla disparada por incidente.
- **`core-python/src/sentinel_dispatch/domain/triaje/tipos.py`** con enums `NivelSangrado`, `NivelDolorToracico`, `GrupoEtario` + dataclass `RespuestaTriaje` actualizado.
- **`core-python/src/sentinel_dispatch/domain/triaje/arbol.py`** con función `clasificar_mpds` implementando las 9 reglas en orden, citando determinantes MPDS en docstrings.
- **Tests UT** (a escribir en H1): mínimo 9 tests cubren las 9 reglas + 12 tests cubren el dataset completo + tests de borde (consciente con todas las variables en `Ninguno` → Alpha; combinaciones cruzadas).

## Referencias

- [Medical Priority Dispatch System — Wikipedia](https://en.wikipedia.org/wiki/Medical_Priority_Dispatch_System) — estructura de 36 protocolos y determinantes.
- [Determinant Codes — IAED Journal](https://www.iaedjournal.org/determinant-codes) — semántica de los niveles A/B/C/D/E.
- [Protocol 26 — IAED Journal](https://www.iaedjournal.org/protocol-26) — referencia de un protocolo MPDS específico.
- [Take A Stab — IAED Journal](https://www.iaedjournal.org/take-a-stab) — Protocol 21 Hemorrhage determinantes.
- [The Medical Priority Dispatch System's ability to predict cardiac arrest outcomes — PubMed](https://pubmed.ncbi.nlm.nih.gov/18562077/) — validación de Protocol 10 Chest Pain.
- [Modelo Nacional Sistema de Atención Médica de Urgencia SAMU — MINSAL Chile](https://www.minsal.cl/wp-content/uploads/2018/03/Modelo-Nacional-Sistema-de-Atenci%C3%B3n-M%C3%A9dica-de-Urgencia-SAMU.pdf) — 5 niveles C1–C5 del Ministerio de Salud.
- [Triage de 5 niveles en Chile — BioBioChile](https://www.biobiochile.cl/noticias/nacional/chile/2023/05/06/triage-de-5-niveles-como-se-priorizan-las-atenciones-de-urgencia-medica-en-chile-y-como-se-clasifican.shtml) — adaptación chilena del ESI.
- [SRS sec. 2.5, 2.6-A, 2.12](../../../../../Celaeno/Proyectos/Sentinel-Dispatch/Entregables/SRS/SRS_Sentinel-Dispatch.pdf) — fuente normativa actualizada.
- [ADR-0006 — Ports & Adapters](0006-ports-and-adapters.md) — define dónde vive el árbol (`domain/triaje/`).
- [ADR-0008 — Validación dual Java vs Python](0008-validacion-dual-java-python.md) — el árbol refinado se porta también a `core-java/`.
