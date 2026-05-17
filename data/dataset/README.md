# Dataset de aceptación

Dataset compartido por `core-python/` y `core-java/` para la validación dual RT-02 (ver SRS sec. 2.16). Ambos cores leen exactamente estos archivos y sus outputs se comparan en `tools/compare_outputs.py`.

## Archivos

- **`incidentes.json`** — 12 incidentes del SRS sec. 2.12. Cubren las 5 categorías MPDS con distribución orientada a casos de alto riesgo.
- **`unidades.json`** — 10 unidades U01..U10 con bases en la conurbación La Serena-Coquimbo. Mix 6 Avanzadas / 4 Básicas.

## Schema

Validado contra `docs/data-model.md` y `core-python/src/sentinel_dispatch/domain/triaje/tipos.py`.

### Incidente

```json
{
  "id": "I-NN",
  "lat": -29.910000,
  "lon": -71.256000,
  "timestamp": "2026-05-25T08:15:00-04:00",
  "respuestas_triaje": { ... 6 campos del SRS sec. 2.5 ... },
  "ground_truth": {
    "categoria_mpds": "Alpha|Bravo|Charlie|Delta|Echo",
    "unidad_esperada": "UNN",
    "eta_aprox_min": 3,
    "regla_aplicada": 1,
    "nota": "..."
  }
}
```

`ground_truth` es metadata de aceptación: el sistema en runtime nunca lo lee. Sirve solo para tests y para comparar outputs reales vs esperados.

### Unidad

```json
{
  "id": "UNN",
  "patente": "AMB-NNN",
  "tipo": "Avanzada|Básica",
  "base_nombre": "...",
  "base_lat": -29.9077,
  "base_lon": -71.2535,
  "estado": "Disponible|EnRuta|EnEscena|Taller"
}
```

## Convenciones aplicadas

### Defaults para campos no explicitados en el SRS sec. 2.12

El SRS describe cada incidente listando solo los campos relevantes ("consciente=Sí; sangrado=Moderado; adulto"). El dataclass `RespuestaTriaje` exige los 6 campos siempre. Aplicamos defaults equivalentes a "no preguntado / negativo", coherentes con cómo MPDS real maneja Key Questions no activadas:

| Campo no mencionado | Default | Justificación |
|---|---|---|
| `sangrado` | `"Ninguno"` | Sin hemorragia observable → Protocol 21 no activado |
| `dolor_toracico` | `"Ninguno"` | No reportado → Protocol 10 no activado |
| `dificultad_respiratoria` | `false` | No reportada → Protocol 6 no activado |
| `respira_normal` (con `consciente=true`) | `true` | El árbol no consulta este campo cuando `consciente=true` |
| `grupo_etario` | `"Adulto"` | Distribución epidemiológica EMS (~65-70% adultos) |

### Timestamps

Una jornada simulada el 2026-05-25 con horas escalonadas a lo largo del día (08:15 → 21:19). Sirve para que CP-02 (factor_hora) tenga incidentes en distintas franjas. CP-02 sobreescribe el timestamp de I-10 a 07:30 y 02:00 sin tocar este archivo.

## Notas

- **Coordenadas de bases de unidades:** corresponden a establecimientos de salud reales (hospitales y CESFAM) de la conurbación La Serena-Coquimbo, ubicados con precisión de referencia tipo Google Maps. Son los puntos de partida para el cálculo A\*; SAMU Chile no publica sus bases operativas reales abiertamente, así que estos establecimientos son la mejor aproximación pública defendible para un proyecto académico.
- **Patentes:** formato `AMB-NNN` simbólico, no patentes chilenas reales (formato `BB-CC-NN` o `BBBB-NN`). Decisión deliberada: evitar coincidencia accidental con vehículos reales.

## Referencias

- SRS sec. 2.5 (entradas del operador), sec. 2.6-A (árbol MPDS-subset), sec. 2.12 (dataset de prueba), sec. 2.16 (validación dual).
- ADR-0008 — Validación dual Java vs Python.
- ADR-0009 — Refinamiento del árbol MPDS-subset.
- `docs/data-model.md` — entidades del dominio.
