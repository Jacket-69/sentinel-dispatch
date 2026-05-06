# Criterios de aceptación — Sentinel-Dispatch

> **Estado:** placeholder. Formato Given-When-Then por historia. Derivado de los 12 CPs del SRS.

## HU-01 — Triaje

- **Dado** un incidente con respuestas `consciente=No, respira=No`,
  **cuando** el operador completa el árbol,
  **entonces** el sistema asigna categoría `Echo` (CP del dataset I-10).

## HU-02 — Ruteo y costo

- **Dado** Charlie + U02 (Básica) a 1.5 km y U01 (Avanzada) a 2.2 km,
  **cuando** se calcula el costo,
  **entonces** se selecciona U01 porque `T(U02) + 600 > T(U01)` (CP-04).

(Resto pendiente F2.)
