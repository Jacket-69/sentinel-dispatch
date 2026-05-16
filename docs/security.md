# Seguridad — baseline

> **Estado:** versión académica. Threat model embebido (no archivo aparte por simplicidad).

## Principios

- Secrets fuera del repo (`.env` ignorado; `.env.example` documenta nombres).
- Principio de menor privilegio.
- Validación de input en backend (Pydantic), no solo frontend.
- Autorización explícita por recurso.
- No loguear tokens, passwords ni datos sensibles del paciente.
- HTTPS obligatorio en deploy demo.

## Threat model académico (resumen STRIDE liviano)

| STRIDE | Riesgo | Mitigación |
|---|---|---|
| **Spoofing** | Operador no autorizado ingresa al sistema | Auth básica (RN-10); proyecto académico → JWT simple |
| **Tampering** | Modificación de log de despacho | Log append-only enforced en BD (RN-03, RN-07) |
| **Repudiation** | Operador niega autorizar despacho | `operador` registrado en cada log |
| **Information disclosure** | Exposición de datos del paciente | No persistir nombres/RUT; solo coordenadas y respuestas binarias del triaje |
| **Denial of service** | Saturación con incidentes spam | Fuera de scope académico; rate limit básico opcional |
| **Elevation of privilege** | Operador escalando a admin | RBAC mínimo: rol `operador` no puede modificar inventario |

## Riesgos del SRS relacionados

- **R-04** Confusión metros/km: tipos fuertes en código + tests unitarios de conversión.
- **R-07** Mismatch crítico: flag `despacho_suboptimo` + alerta visual roja (RN-02).
- **R-08** Subset MPDS no certificado: documentado explícitamente; fuera de uso clínico real.

## Secrets

Variables de entorno en `.env` (nunca commiteado). Únicos secretos del proyecto:

- `APP_SECRET_KEY` — firma de cookies/sesiones.

(No hay tokens de APIs externas en v1; OSM se carga offline.)
