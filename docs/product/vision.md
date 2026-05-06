# Visión

> **Estado:** stub — pendiente F1 (Descubrimiento). Plantilla en `Recursos/Procesos/Metodología de Proyectos/Estructura de docs.md` del vault.

## Problema

Los servicios de emergencia médica prehospitalaria (SAMU) en la IV Región despachan unidades basándose en intuición del operador o distancia euclidiana. Esto produce:

- Tiempos de llegada calculados sobre línea recta que ignoran la red vial real.
- Mismatch entre criticidad clínica del paciente y tipo de unidad (Avanzada vs Básica).
- Decisiones no auditables ni reproducibles.

## Usuarios

- **Operador de Despacho** — ingresa incidente y árbol de triaje, confirma despacho.
- **Personal de Unidad** — recibe asignación, actualiza estado.
- **Administrador de Flota** — gestiona inventario y bases.
- **Auditor** — consulta logs inmutables.

## Propuesta de valor

Sistema que selecciona la unidad óptima en <1 s usando triaje clínico estructurado (MPDS-subset), ruteo A* sobre OSM real y función de costo justificada que pondera tiempo + idoneidad clínica.

## Éxito

- 100% de los 12 incidentes del dataset clasifican correctamente (sec. 2.12 SRS).
- Echo/Delta nunca asignados a unidad Básica salvo flag `despacho_suboptimo` activo (CP-05).
- Ruteo A* dentro de ±5% de OSRM en 95% de muestras (CP-01).
- Cálculo completo ≤1 s para flota de 50 unidades.

## Fuera de alcance v1

- MEXCLP / optimización de cobertura (R-03, ADR futuro).
- Integración con datos de tráfico en tiempo real (R-02).
- App móvil para personal de unidad.
- Pago, autenticación social, multi-tenant.
- Certificación clínica MPDS oficial (R-08).
