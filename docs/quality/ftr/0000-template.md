---
ftr: 0000
title: <Tema de la FTR>
date: YYYY-MM-DD
moderador: <nombre>
participantes: [<nombres>]
producto_auditado: <ruta o commit hash>
duracion_minutos: <N>
---

# FTR-NNNN — <tema>

## Producto auditado

<Descripción del producto + commit hash si aplica + alcance específico revisado.>

## Checklist de preparación (completado antes de la reunión)

- [ ] Lectura completa del producto por cada participante
- [ ] Identificación previa de al menos 3 puntos de observación cada uno
- [ ] Revisión de RFs y RNFs relacionados del SRS
- [ ] Lectura del ADR asociado si aplica

## Hallazgos

| ID | Tipo | Severidad | Descripción | Asignado a | Fecha objetivo |
|---|---|---|---|---|---|
| H-01 | <Defecto/Mejora/Pregunta> | <crítico/mayor/menor> | ... | ... | YYYY-MM-DD |

**Convenciones**:

- **Severidad — crítico**: incumple RF/RNF/RT del SRS. Frena merge del módulo.
- **Severidad — mayor**: compromete mantenibilidad/performance/claridad. Bloquea cierre de hito.
- **Severidad — menor**: estilo, mejora opcional. Backlog general.
- **Tipo — defecto**: error detectado.
- **Tipo — mejora**: optimización no exigida.
- **Tipo — pregunta**: ambigüedad que puede gatillar ADR.

## Decisiones tomadas

- ...

## Acuerdos / follow-ups

- [ ] <acción> — responsable: <nombre> — fecha: YYYY-MM-DD

## Firmas

- Moderador: <nombre> (fecha)
- Participantes: <nombres> (fecha)
