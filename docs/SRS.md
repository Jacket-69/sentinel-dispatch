---
tags: [proyecto, gcs, sentinel-dispatch, srs]
estado: fuente-base
fecha: 2026-04-26
proyecto: Sentinel-Dispatch
ramo: gcs
---

> [!info] Estado normalizado
> La versión entregable vigente quedó normalizada el 2026-05-06 en `SRS_Sentinel-Dispatch.tex` y `SRS_Sentinel-Dispatch.pdf`.
> Este Markdown se mantiene como fuente navegable del vault; los `.doc`/`.docx` anteriores fueron movidos a `backups/normalizacion_srs_20260506/`.

# PROYECTO: SISTEMAS CRÍTICOS – GESTIÓN DE CALIDAD DE SOFTWARE

**Carrera:** Ingeniería Civil en Computación e Informática
**Asignatura:** Gestión de Calidad de Software

---

## 2.1 Portada

**Nombre del sistema:** Sentinel-Dispatch — Motor de Despacho Eficiente de Unidades de Emergencia Médica
**Integrantes:** Benjamín López y Fernando Godoy M.
**Fecha:** Abril 2026

---

## 2.2 Contexto del Sistema

### Problema que busca resolver

Los servicios de emergencia médica prehospitalaria (SAMU) deben despachar, ante cada incidente, la unidad más apta considerando simultáneamente el tiempo real de llegada por la red vial, la idoneidad clínica de la unidad disponible (avanzada vs. básica) y el nivel de criticidad del paciente derivado del árbol de triaje. Los métodos actuales basados en la intuición del operador o en distancia euclidiana fallan sistemáticamente: una unidad aparentemente cercana en línea recta puede estar a 15 minutos de viaje real por la red vial de La Serena-Coquimbo; despachar una unidad básica a un paro cardiorrespiratorio genera daño clínico irreversible.

### Por qué es crítico

Un retraso de 1 minuto en la atención de un paro cardíaco reduce aproximadamente un 10% la probabilidad de sobrevida (NFPA 1710 establece como estándar que la primera unidad ALS llegue en ≤ 8 minutos al 90% de los incidentes). Un mismatch de tipo de unidad —básica BLS despachada a un incidente Echo— se traduce en deterioro clínico irreversible y responsabilidad civil del servicio. La decisión de despacho se toma bajo presión extrema, en segundos, y con consecuencias que no pueden revertirse.

### Qué consecuencias tendría un error

- **Error leve:** unidad sub-óptima despachada pero con tiempo de llegada aceptable → recursos mal asignados, zona de origen queda descubierta.
- **Error grave:** unidad básica (BLS) despachada a incidente Echo o Delta crítico → el paciente no recibe maniobras avanzadas → muerte evitable, responsabilidad civil del operador y del servicio.
- **Error de datos:** coordenadas mal ingresadas → ETA calculado sobre ruta falsa, unidad llega a ubicación incorrecta → retraso no recuperable.
- **Error de cobertura:** sacar la única unidad disponible de una zona geográfica deja esa área sin respuesta durante el trayecto.

---

## 2.3 Objetivo del Sistema

El sistema debe **calcular automáticamente la unidad óptima a despachar** ante un incidente de emergencia médica, en función de:

1. **Tiempo real de llegada** estimado mediante el algoritmo A* sobre el grafo vial OSM de la IV Región de Coquimbo, con pesos calibrados por velocidad efectiva según tipo de vía, factor temporal y factor sirena.
2. **Idoneidad clínica** de la unidad respecto a la categoría MPDS del incidente (Alpha / Bravo / Charlie / Delta / Echo), derivada automáticamente del árbol de triaje.
3. **Política de re-despacho** con confirmación humana cuando llega un incidente de mayor criticidad que el que una unidad está atendiendo.

El sistema entrega, en menos de 1 segundo desde la confirmación del operador: la unidad asignada, el ETA, la ruta completa y el log inmutable de la decisión.

---

## 2.4 Usuarios del Sistema

| Usuario | Rol |
|---|---|
| Operador de Despacho | Ingresa los datos del incidente (ubicación + respuestas al árbol de triaje), confirma el despacho sugerido por el sistema y autoriza re-despachos |
| Personal de Unidad | Recibe la asignación en su dispositivo, actualiza el estado de la unidad (En Ruta / En Escena / Liberada) |
| Administrador de Flota | Gestiona el inventario de unidades, sus capacidades (Avanzada / Básica), bases de operación y estados de mantenimiento |
| Auditor | Consulta y exporta los logs inmutables de despacho para revisión operativa o legal |

---

## 2.5 Entradas del Sistema

### Entradas del operador

| Variable | Rango válido | Unidad | Observación |
|---|---|---|---|
| Latitud del incidente | −30.5 a −29.5 | grados decimales | 6 decimales de precisión; rango IV Región de Coquimbo |
| Longitud del incidente | −71.7 a −70.5 | grados decimales | 6 decimales de precisión; rango IV Región de Coquimbo |
| Respuesta: ¿El paciente está consciente? | {Sí, No} | booleana | Pre-pregunta del árbol (cf. MPDS Protocol 31) |
| Respuesta: ¿El paciente respira con normalidad? | {Sí, No} | booleana | Aplica si consciente = No; distingue 31-D-2 vs 9-E-1 / 31-E-1 |
| Respuesta: Nivel de sangrado visible | {Ninguno, Moderado, Activo, Peligroso} | categórica | Mapeo a MPDS Protocol 21: A-1/A-2 (sin nivel) → B-2 (Moderado) → adaptación SAMU (Activo) → D-4 (Peligroso). *Peligroso* se refiere a sangrado arterial o en zonas críticas (axila, ingle, cuello). |
| Respuesta: Dolor torácico | {Ninguno, Presente, Crítico} | categórica | Mapeo a MPDS Protocol 10: sin (no aplica) → 10-C (Presente, alerta sin síntomas asociados graves) → 10-D (Crítico, con not-alert / abnormal breathing / clammy u otro síntoma asociado severo) |
| Respuesta: ¿Dificultad respiratoria? | {Sí, No} | booleana | Mapeo a MPDS Protocol 6 (Breathing Problems) / 31-C-1 (Alert with abnormal breathing) |
| Respuesta: Grupo etario del paciente | {Pediátrico (<14 a), Adulto (14–64 a), Anciano (≥65 a)} | categórica | Modificador de riesgo; reservado para subdeterminantes específicos (ej. 6-D-1 pediátrico). No entra al árbol v1. |
| Hora del incidente | Timestamp ISO 8601 | — | Para cálculo de factor_hora en A* |

### Estado leído del sistema (no ingresado por el operador)

| Variable | Rango válido | Unidad | Observación |
|---|---|---|---|
| Estado de cada unidad | {Disponible, EnRuta, EnEscena, Taller} | categórica | Leído del estado del sistema en tiempo real |
| Tipo de unidad | {Avanzada, Básica} | categórica | Registrado en el inventario de flota |
| Posición de cada unidad | (lat, lon) | grados decimales | Origen del cálculo A* para unidades Disponibles |

> [!note] La categoría MPDS **no** es ingresada directamente por el operador. Es derivada automáticamente por el sistema tras completar el árbol de triaje (sección 2.6-A). Esto elimina el error humano en la clasificación.

---

## 2.6 Procesamiento y Lógica de Cálculo

### A. Triaje — Árbol MPDS-subset

El sistema aplica un árbol de decisión categórica inspirado en el protocolo Medical Priority Dispatch System (MPDS), documentado como subset no certificado. Las categorías y niveles MPDS se mantienen literales (Alpha → Bravo → Charlie → Delta → Echo); los chief complaints individuales (36 protocolos en MPDS) se compactan en un árbol único de 9 reglas con variables categóricas equivalentes (ver sección **A.1 Mapeo con MPDS oficial**). Las respuestas del operador determinan la categoría del incidente:

| Categoría | Color | Descripción clínica | Unidad mínima requerida |
|---|---|---|---|
| Alpha | 🟢 Verde | No urgente; el paciente puede esperar | Básica o Avanzada |
| Bravo | 🟡 Amarillo | Potencialmente urgente; síntomas leves | Básica o Avanzada |
| Charlie | 🟠 Naranja | Urgente; posible deterioro | Básica (penalizada) o Avanzada |
| Delta | 🔴 Rojo | Grave; riesgo vital inminente | Solo Avanzada |
| Echo | 🔴 Rojo crítico | Paro / inconsciente / no respira | Solo Avanzada |

**Lógica del árbol (9 reglas en orden de evaluación):**

```
1. consciente = No  Y  respira_normal = No                    → Echo
2. consciente = No  Y  respira_normal = Sí                    → Delta
3. consciente = Sí  Y  sangrado = Peligroso                   → Delta
4. consciente = Sí  Y  dolor_toracico = Crítico               → Delta
5. consciente = Sí  Y  dolor_toracico = Presente              → Charlie
6. consciente = Sí  Y  dificultad_respiratoria = Sí           → Charlie
7. consciente = Sí  Y  sangrado = Activo                      → Charlie
8. consciente = Sí  Y  sangrado = Moderado                    → Bravo
9. consciente = Sí  Y  (resto)                                → Alpha
```

Las reglas se evalúan en orden estricto: la primera que satisface sus condiciones determina la categoría. Por construcción cubren los 12 incidentes del dataset (sec. 2.12).

### A.1 Mapeo con MPDS oficial

Cada regla del árbol corresponde a un determinante MPDS reconocido:

| Regla | Condición | MPDS oficial / fundamento |
|---|---|---|
| 1 | Inconsciente sin respiración normal → Echo | Protocol 9-E-1 (Cardiac/Respiratory Arrest) o 31-E-1 (Ineffective breathing) |
| 2 | Inconsciente con respiración normal → Delta | Protocol 31-D-2 (Unconscious — effective breathing) |
| 3 | Sangrado peligroso → Delta | Protocol 21-D-4 (Dangerous hemorrhage). *Peligroso* = sangrado arterial o en zonas críticas (axila, ingle, cuello). |
| 4 | Dolor torácico crítico → Delta | Protocol 10-D (Chest pain con síntoma asociado severo: not alert / abnormal breathing / clammy / irradiación severa). |
| 5 | Dolor torácico presente → Charlie | Protocol 10-C (Chest pain aislado, paciente alerta sin síntomas asociados graves). |
| 6 | Dificultad respiratoria → Charlie | Protocol 6-C (Breathing problems, alerta) / Protocol 31-C-1 (Alert with abnormal breathing). |
| 7 | Sangrado activo → Charlie | **Adaptación SAMU Chile**. Sangrado uncontrolled sin verificación de ubicación geográfica se eleva sistemáticamente a Charlie como precaución (lectura conservadora vs. MPDS 21-B-2 literal). Coherente con el modelo de 5 niveles C1–C5 del Ministerio de Salud (Chile, 2018). |
| 8 | Sangrado moderado → Bravo | Protocol 21-B-2 (Serious hemorrhage, uncontrolled pero no en zona peligrosa). |
| 9 | Sin Chief Complaint que escale → Alpha | Nivel base; equivalente a Protocol 26-A (Sick Person) sin determinantes específicos. |

> [!warning] Este árbol es un **subset inspirado en MPDS**, no el protocolo oficial certificado por Priority Dispatch Corp. Está documentado explícitamente como tal (ver R-08). No debe usarse en sistemas de salud reales sin certificación. La regla 7 incorpora una adaptación documentada al contexto SAMU Chile justificada en la decisión arquitectónica ADR-0009.

### B. Ruteo A* sobre grafo OSM

El sistema construye en memoria el grafo vial de la IV Región a partir de datos OpenStreetMap (OSM). Cada arista del grafo tiene el peso:

```
peso(arista) = longitud_m / velocidad_efectiva_m_s
```

donde:

```
velocidad_efectiva_m_s = maxspeed_OSM_kmh × (1000/3600) × factor_hora(t) × factor_sirena
```

**factor_hora** — perfil temporal estático calibrado para La Serena-Coquimbo:

| Rango horario | factor_hora | Justificación |
|---|---|---|
| 00:00–05:59 | 1.00 | Tráfico mínimo nocturno |
| 06:00–08:59 | 0.60 | Punta mañana |
| 09:00–11:59 | 0.85 | Post-punta moderado |
| 12:00–13:59 | 0.70 | Punta mediodía |
| 14:00–17:59 | 0.80 | Tarde moderada |
| 18:00–20:59 | 0.65 | Punta tarde/noche |
| 21:00–23:59 | 0.95 | Noche baja |

> [!note] Hora exactamente en frontera de banda (ej. 09:00:00) se asigna al tramo de inicio (09:00–11:59, factor = 0.85). Ver CL-08.

**factor_sirena = 1.4** — la sirena multiplica la velocidad efectiva por 1.4, lo que equivale a una reducción del tiempo de viaje de aproximadamente 28.6% (1 − 1/1.4). Esta magnitud es consistente con Petzäll et al. (2011) *"Effects of sirens on clearance times in Swedish pre-hospital care"* y Brown et al. (2000) *"Time in prehospital care: the effect of lights and sirens"*, que reportan reducciones del orden de 1–3 minutos en transporte urbano (~25–35% según la ruta). Se aplica a todas las unidades en estado de emergencia activa.

**Heurística A\*:** `h(n) = haversine(n, destino) / v_max`, con `v_max = 38.89 m/s` (140 km/h, equivalente a la mayor `maxspeed_OSM` legal de la región multiplicada por `factor_sirena`). Esta heurística es admisible porque ningún tramo del grafo puede recorrerse a velocidad efectiva superior a `v_max`, por lo que `h(n)` nunca sobreestima el costo real en segundos. La admisibilidad garantiza que A* devuelva la ruta óptima.

### C. Función de costo de despacho

Para cada unidad `u` candidata (estado = Disponible) y el incidente `i`:

```
Costo(u, i) = α · T_viaje(u→i) + β · Penalización_Idoneidad(u, i)
```

- **α = 1.0** (peso dimensional de tiempo, adimensional; `T_viaje` ya está en segundos)
- **β = 600 segundos** — convierte la penalización adimensional a unidades comparables con `T_viaje`. El mismatch clínico equivale a 10 minutos de penalización; justificado porque un re-despacho desde la unidad incorrecta tarda en promedio 8–12 minutos adicionales en condiciones urbanas, más el deterioro clínico acumulado.

> [!note] El término `γ · ΔCobertura(u)` (degradación MEXCLP, Daskin 1983) está diseñado pero excluido de la v1 — ver R-03 y la decisión [2026-04-26] MEXCLP fuera de v1. La función de costo de v1 considera solo tiempo e idoneidad.

**Tabla de Penalización_Idoneidad** (adimensional):

| Categoría incidente | Tipo unidad | Penalización_Idoneidad | β · Penalización (s) | Nota |
|---|---|---|---|---|
| Echo | Avanzada | 0 | 0 | Asignación óptima |
| Echo | Básica | ∞ | ∞ | No se despacha; ver regla RN-02 |
| Delta | Avanzada | 0 | 0 | Asignación óptima |
| Delta | Básica | ∞ | ∞ | No se despacha |
| Charlie | Avanzada | 0 | 0 | Asignación óptima |
| Charlie | Básica | 1 | 600 | Penalización por idoneidad reducida |
| Bravo | Avanzada o Básica | 0 | 0 | Ambas aptas |
| Alpha | Avanzada o Básica | 0 | 0 | Ambas aptas |

**Selección:** `Despacho = argmin_u Costo(u, i)` sobre todas las unidades con estado = Disponible.

**Empate:** si dos o más unidades alcanzan el mismo costo mínimo, se selecciona la de menor ID lexicográfico (desempate determinista y reproducible). Ver CL-02.

### D. Política de re-despacho

Una unidad `u` actualmente EnRuta hacia el incidente `i_actual` puede ser reasignada a un nuevo incidente `j` si se cumplen **todas** las condiciones:

1. `categoria(j) > categoria(i_actual)` en orden estricto Echo > Delta > Charlie > Bravo > Alpha
2. `progreso_actual(u) ≤ 50%` del trayecto original hacia `i_actual`
3. Existe al menos otra unidad `u'` tal que `Costo(u', i_actual) < ∞`

El re-despacho **no es automático**: el sistema presenta la propuesta al operador de despacho, quien debe confirmarla explícitamente. El sistema registra en el log tanto la propuesta como la decisión del operador (aceptada / rechazada).

---

## 2.7 Reglas de Negocio

- **RN-01 — Validación de rango:** coordenadas fuera del rango de la IV Región (lat −30.5 a −29.5; lon −71.7 a −70.5) son rechazadas con mensaje de error descriptivo antes de ejecutar cualquier cálculo.
- **RN-02 — Saturación crítica (Echo/Delta + única unidad Básica):** si la única unidad Disponible es Básica y el incidente es Echo o Delta, el sistema **escala alerta** (despacha igual con flag rojo "Despacho sub-óptimo crítico — unidad inadecuada") en lugar de bloquear el despacho. El operador puede anular. El evento queda registrado con campo especial `despacho_suboptimo: true` en el log.
- **RN-03 — Log inmutable:** cada despacho genera un registro JSON inmutable con todos los campos del cálculo. Solo se permite agregar eventos posteriores (cancelación, finalización, re-despacho) como entradas adicionales; nunca editar ni eliminar.
- **RN-04 — Taller excluido:** unidades con estado = Taller no participan en el cálculo bajo ninguna circunstancia.
- **RN-05 — Rendimiento:** el cálculo completo (árbol de triaje + A* + selección de unidad) debe completarse en ≤ 1 segundo para flotas de hasta 50 unidades, y en ≤ 300 ms para flotas de hasta 10 unidades.
- **RN-06 — Confirmación humana de re-despacho:** el sistema propone el re-despacho pero no lo ejecuta sin confirmación explícita del operador de despacho.
- **RN-07 — Append-only de logs:** los logs solo admiten append de nuevos eventos. Cualquier intento de modificar un registro existente debe fallar con error y generar una entrada de alerta en el log de auditoría.
- **RN-08 — Saturación de flota:** si no existen unidades en estado Disponible, el sistema reporta el estado de saturación e identifica las unidades EnRuta con menor progreso de trayecto como candidatas a re-dirección, para consideración del operador.
- **RN-09 — Snap al nodo OSM:** si las coordenadas del incidente son válidas en rango pero no tienen un nodo OSM a menos de 500 m, el sistema realiza snap al nodo más cercano y alerta al operador con la distancia de snap.
- **RN-10 — Autenticación obligatoria:** todas las operaciones (triaje, despacho, consulta de logs, administración de flota) requieren sesión autenticada. El acceso se realiza exclusivamente por HTTPS.

---

## 2.8 Salidas Esperadas

- **ID de despacho único** — formato `SD-YYYYMMDD-NNNN` (ej. `SD-20260426-0012`)
- **Unidad asignada** — patente y tipo (Avanzada / Básica)
- **ETA** — en segundos (entero) y formato HH:MM legible
- **Ruta** — lista ordenada de coordenadas (lat, lon) del path A* completo
- **Costo desglosado** — T_viaje en segundos, penalización en segundos equivalentes, costo total
- **Categoría MPDS asignada** — Alpha / Bravo / Charlie / Delta / Echo
- **Timestamp ISO 8601** — fecha y hora exacta del cálculo
- **Alerta visual** — si el despacho es sub-óptimo (Básica para Echo o Delta), se muestra alerta roja con texto "Despacho sub-óptimo crítico"
- **Log JSON inmutable** — persistido en la base de datos con todos los campos anteriores más las respuestas individuales del árbol de triaje

**Ejemplo de log JSON mínimo:**

```json
{
  "id": "SD-20260426-0012",
  "timestamp": "2026-04-26T14:32:07-04:00",
  "incidente": {
    "lat": -29.906712,
    "lon": -71.254831,
    "categoria_mpds": "Echo",
    "respuestas_triaje": { "consciente": false, "respira": false }
  },
  "unidad": { "id": "U03", "patente": "BPJK-34", "tipo": "Avanzada" },
  "eta_segundos": 312,
  "costo_desglosado": { "T_viaje": 312, "penalizacion": 0, "total": 312 },
  "ruta_nodos": [1042311, 1042398, 1043215],
  "despacho_suboptimo": false,
  "operador": "operador_01"
}
```

---

## 2.9 Requisitos Funcionales

| ID | Requisito |
|---|---|
| RF-01 | El sistema permite ingresar las coordenadas del incidente con validación de rango en tiempo real (IV Región de Coquimbo) |
| RF-02 | El sistema ejecuta el árbol de triaje MPDS-subset y asigna automáticamente una de las cinco categorías (Alpha a Echo) |
| RF-03 | El sistema construye el grafo OSM de la IV Región y calcula rutas mediante A* con pesos calibrados (factor_hora + factor_sirena) |
| RF-04 | El sistema calcula la función de costo multiobjetivo `Costo(u, i) = α·T_viaje + β·Penalización_Idoneidad` para cada unidad Disponible |
| RF-05 | El sistema selecciona la unidad óptima por `argmin_u Costo(u, i)` y presenta la propuesta al operador con ETA y ruta |
| RF-06 | El sistema genera y persiste el log inmutable JSON de cada despacho confirmado, con todos los campos del cálculo |
| RF-07 | El sistema visualiza la ruta A* sobre un mapa interactivo con la posición del incidente y la unidad asignada |
| RF-08 | El sistema evalúa las condiciones de re-despacho y, cuando se cumplen, propone al operador reasignar una unidad EnRuta, registrando la decisión |
| RF-09 | El sistema muestra un panel de unidades con su estado en tiempo real (Disponible / EnRuta / EnEscena / Taller) y posición aproximada |
| RF-10 | El sistema detecta saturación de flota (sin unidades Disponibles) y reporta el estado con sugerencia de candidatas a re-dirección |
| RF-11 | El sistema permite exportar los logs de despacho en formato CSV y JSON para auditoría externa |
| RF-12 | El sistema ofrece un modo de simulación que ejecuta el cálculo completo sobre un estado de flota ficticio sin afectar el estado operativo real |

---

## 2.10 Requisitos de Calidad

| Atributo | Requisito |
|---|---|
| **Precisión de ruteo** | El tiempo de ruta calculado por A* debe coincidir con el calculado por OSRM (oracle externo sobre el mismo grafo OSM) con un error ≤ 5% en el 95% de una muestra de 100 rutas aleatorias dentro de la IV Región |
| **Confiabilidad** | El sistema debe estar disponible el 99,9% del tiempo en horario operativo (equivale a ≤ 8,76 horas de downtime anual) |
| **Rendimiento — flota grande** | El cálculo completo (triaje + A* + selección) se completa en ≤ 1 segundo para flotas de hasta 50 unidades simultáneas |
| **Rendimiento — flota pequeña** | El cálculo completo se completa en ≤ 300 ms para flotas de hasta 10 unidades simultáneas |
| **Trazabilidad** | Cada despacho confirmado persiste su log con todas las variables del cálculo: respuestas de triaje, categoría MPDS, costos por unidad, unidad seleccionada, ETA, ruta y timestamp |
| **Tolerancia a errores** | Coordenadas fuera del rango IV Región son rechazadas con mensaje descriptivo antes de ejecutar cualquier cálculo; el sistema nunca entrega resultado sobre entrada inválida |
| **Usabilidad** | Un operador entrenado completa el árbol de triaje (ingreso de coordenadas + respuestas) en ≤ 90 segundos bajo condiciones normales de operación |
| **Seguridad** | Todas las operaciones requieren autenticación; los logs son inmutables post-guardado; la comunicación se realiza exclusivamente por HTTPS |

---

## 2.11 Casos Límite

| ID | Caso | Entrada | Comportamiento esperado |
|---|---|---|---|
| CL-01 | Sin unidades Disponibles | Todas las unidades en estado EnRuta, EnEscena o Taller | Sistema reporta saturación; muestra candidatas a re-dirección ordenadas por menor progreso de trayecto; no genera despacho automático |
| CL-02 | Empate exacto en costo | Dos unidades con T_viaje idéntico y misma penalización | Se selecciona la unidad con menor ID lexicográfico (ej. U02 antes que U05) |
| CL-03 | Coordenada en frontera del rango IV Región | lat = −30.5000000 (valor límite exacto) | Coordenada aceptada (el rango es inclusivo en ambos extremos) |
| CL-04 | Echo con única unidad Básica Disponible | categoría = Echo, única unidad = Básica | Sistema despacha con flag rojo "Despacho sub-óptimo crítico"; campo `despacho_suboptimo: true` en el log |
| CL-05 | Re-despacho denegado por progreso | Unidad U01 EnRuta al 60% hacia incidente i1; llega nuevo incidente j1 categoría Echo | Sistema evalúa condición (60% > 50%): re-despacho denegado; operador es notificado; sistema busca otra unidad para j1 |
| CL-06 | Re-despacho permitido por progreso | Unidad U01 EnRuta al 40% hacia incidente i1; llega nuevo incidente j1 categoría Echo; existe U02 Disponible para i1 | Sistema propone re-despacho de U01 a j1 y asignación de U02 a i1; espera confirmación del operador |
| CL-07 | Sin ruta OSM entre origen y destino | Coordenada de incidente en isla o zona sin conectividad vial cargada | Sistema reporta "Sin ruta disponible en grafo OSM" y sugiere snap al nodo conectado más cercano; no genera ETA |
| CL-08 | Hora exactamente en frontera de factor_hora | Timestamp = 2026-04-26T09:00:00 | Se aplica factor_hora = 0.85 (tramo 09:00–11:59); nunca el tramo anterior |
| CL-09 | Snap al nodo OSM > 500 m | Coordenadas válidas en rango pero sin nodo OSM a menos de 500 m | Sistema realiza snap al nodo más cercano y muestra alerta: "Incidente snapeado a X m del punto indicado — confirmar ubicación" |
| CL-10 | Pérdida de estado de unidad durante cálculo | Timeout al leer inventario de flota en mitad del cálculo | Sistema aborta el cálculo, lanza error descriptivo, no persiste log parcial; solicita reintentar |

---

## 2.12 Dataset de Prueba (12 incidentes)

El dataset cubre las cinco categorías MPDS con distribución orientada a los casos de mayor riesgo. Las unidades de referencia son U01–U10, con bases en la conurbación La Serena-Coquimbo.

**Inventario de unidades (estado inicial del dataset):**

| ID | Tipo | Base (lat, lon) | Estado inicial |
|---|---|---|---|
| U01 | Avanzada | −29.902000, −71.252000 | Disponible |
| U02 | Básica | −29.916500, −71.259000 | Disponible |
| U03 | Avanzada | −29.934000, −71.280000 | Disponible |
| U04 | Básica | −29.888000, −71.245000 | Disponible |
| U05 | Avanzada | −29.956000, −71.337000 | Disponible |
| U06 | Básica | −29.872000, −71.231000 | Disponible |
| U07 | Avanzada | −29.944000, −71.305000 | Disponible |
| U08 | Básica | −29.921000, −71.268000 | Disponible |
| U09 | Avanzada | −29.897000, −71.261000 | Disponible |
| U10 | Básica | −29.963000, −71.351000 | Disponible |

**Incidentes simulados:**

| #    | Lat        | Lon        | Respuestas triaje (resumen)                                         | Categoría esperada | Unidad esperada                | ETA aprox. | Nota                                                  |
| ---- | ---------- | ---------- | ------------------------------------------------------------------- | ------------------ | ------------------------------ | ---------- | ----------------------------------------------------- |
| I-01 | −29.910000 | −71.256000 | consciente=Sí; sangrado=Ninguno; dolor_toracico=Ninguno; dif_respiratoria=No; adulto | Alpha   | U02 (Básica más cercana)       | ~3 min     | Regla 9 (sin Chief Complaint que escale); Básica válida |
| I-02 | −29.925000 | −71.263000 | consciente=Sí; sangrado=Moderado; adulto                                              | Bravo   | U08 (Básica más cercana)       | ~2 min     | Regla 8 → 21-B-2 (serious hemorrhage); cualquier unidad válida |
| I-03 | −29.940000 | −71.275000 | consciente=Sí; sangrado=Moderado; anciano                                             | Bravo   | U03 (Avanzada próxima)         | ~1 min     | Regla 8 → 21-B-2; Avanzada sin penalización             |
| I-04 | −29.900000 | −71.248000 | consciente=Sí; sangrado=Activo; dolor_toracico=Ninguno                                | Charlie | U01 (Avanzada; 0 penalización) | ~2 min     | Regla 7 (adaptación SAMU); Básica penalizada +600 s → Avanzada gana |
| I-05 | −29.950000 | −71.320000 | consciente=Sí; dif_respiratoria=Sí; anciano                                           | Charlie | U05 (Avanzada próxima)         | ~4 min     | Regla 6 → 31-C-1 / 6-C; validar penalización vs Básica |
| I-06 | −29.918000 | −71.262000 | consciente=Sí; dolor_toracico=Presente                                                | Charlie | U09 (Avanzada)                 | ~3 min     | Regla 5 → 10-C (chest pain alerta); penalización Básica confirmada |
| I-07 | −29.904000 | −71.253000 | consciente=No; respira_normal=Sí                                                      | Delta   | U01 (Avanzada)                 | ~2 min     | Regla 2 → 31-D-2 (unconscious effective breathing); solo Avanzada |
| I-08 | −29.938000 | −71.285000 | consciente=Sí; dolor_toracico=Crítico; adulto                                         | Delta   | U03 (Avanzada)                 | ~1 min     | Regla 4 → 10-D (chest pain con síntoma asociado severo); penalización ∞ a Básica |
| I-09 | −29.957000 | −71.340000 | consciente=No; respira_normal=Sí; pediátrico                                          | Delta   | U05 (Avanzada)                 | ~2 min     | Regla 2 → 31-D-2; Avanzada obligatoria                 |
| I-10 | −29.907000 | −71.257000 | consciente=No; respira_normal=No                                                      | Echo    | U01 (Avanzada más cercana)     | ~2 min     | Regla 1 → 9-E-1 / 31-E-1 (paro / ineffective breathing); solo Avanzada |
| I-11 | −29.942000 | −71.298000 | consciente=No; respira_normal=No                                                      | Echo    | U07 (Avanzada próxima)         | ~3 min     | Regla 1; validar que no se despacha Básica             |
| I-12 | −29.895000 | −71.247000 | consciente=No; respira_normal=No; anciano                                             | Echo    | U09 (Avanzada más cercana)     | ~2 min     | Regla 1; candidato a re-despacho si U09 EnRuta         |

> [!important] Los ETA son aproximaciones para el dataset de prueba. Los valores exactos dependen del grafo OSM cargado y del factor_hora en el momento de la prueba. Los casos de prueba (sección 2.13) definen los criterios de éxito en términos de comparación con oracle OSRM, no de valores absolutos de ETA.

---

## 2.13 Casos de Prueba

| ID | Descripción | Entrada | Resultado esperado | Criterio de éxito |
|---|---|---|---|---|
| CP-01 | Cálculo A* — precisión vs. oracle OSRM | 100 pares origen-destino aleatorios dentro de la IV Región | ETA calculado por A* para cada par | `|T_A* − T_OSRM| / T_OSRM ≤ 0.05` en ≥ 95 de 100 muestras |
| CP-02 | factor_hora aplicado correctamente | Incidente I-10 ingresado a las 07:30 (punta mañana, factor 0.60) vs. 02:00 (nocturno, factor 1.00) | ETA_07:30 = ETA_02:00 × (1.00/0.60) ≈ 1.67 × ETA_02:00 (a mayor congestión, mayor tiempo) | `ETA_07:30 / ETA_02:00 ∈ [1.60, 1.70]` (margen ±5% por ruta) |
| CP-03 | factor_sirena aplicado correctamente | Misma ruta calculada con factor_sirena = 1.4 vs. sin sirena (factor = 1.0) | ETA_sin_sirena = ETA_con_sirena × 1.4 | `ETA_sin_sirena / ETA_con_sirena ∈ [1.38, 1.42]` |
| CP-04 | Penalización de idoneidad — Charlie + Básica | Incidente I-04 (Charlie); U02 Básica a 1.5 km; U01 Avanzada a 2.2 km | U01 seleccionada pese a ser más lejana | Costo(U02) = T_viaje(U02) + 600 > Costo(U01) = T_viaje(U01) + 0 → U01 ganadora |
| CP-05 | Penalización infinita — Echo + Básica | Incidente I-10 (Echo); U02 Básica cercana (1.0 km) y U01 Avanzada lejana (3.5 km) Disponibles | U01 seleccionada; U02 excluida del argmin por penalización ∞ | U02 no aparece en la propuesta de despacho; despacho normal (no sub-óptimo, U01 es Avanzada) |
| CP-06 | Re-despacho permitido — progreso ≤ 50% | U01 EnRuta al 40% hacia I-01; llega I-10 (Echo); U09 Disponible para I-01 | Sistema propone re-despacho de U01 a I-10 y asignación de U09 a I-01 | Propuesta presentada al operador; log registra propuesta con todas las condiciones evaluadas |
| CP-07 | Re-despacho denegado — progreso > 50% | U01 EnRuta al 60% hacia I-01; llega I-10 (Echo) | Sistema no propone re-despacho de U01; busca unidad Disponible para I-10 | Propuesta de re-despacho de U01 ausente; log de evaluación indica "progreso 60% > umbral 50%" |
| CP-08 | Log inmutable — intento de edición | Despacho SD-001 guardado; intento de modificar campo ETA vía API | Error 403 / operación rechazada; log de auditoría registra intento fallido | Registro original sin cambios; entrada de alerta en log de auditoría |
| CP-09 | Validación de coordenadas — fuera de rango | lat = −31.200000, lon = −71.300000 | Rechazo con mensaje "Coordenadas fuera del área de cobertura (IV Región)" | No se ejecuta A* ni cálculo de costo; ningún log de despacho generado |
| CP-10 | Saturación de flota | Todas las unidades en estado EnRuta o EnEscena | Sistema reporta saturación; lista candidatas a re-dirección ordenadas por progreso ascendente | Mensaje de saturación visible; no se genera despacho automático |
| CP-11 | Empate de costo — desempate lexicográfico | Incidente con U03 y U07 (ambas Avanzada) con T_viaje idéntico calculado | U03 seleccionada | ID seleccionado = "U03" (menor lexicográfico respecto a "U07") |
| CP-12 | Performance — flota de 50 unidades | 50 unidades Disponibles (fixture sintético, generado por bench script fuera del dataset de aceptación); incidente Echo ingresado | Cálculo completo completado | Tiempo total (triaje + A* × 50 + argmin) ≤ 1 000 ms medido en servidor de prueba |

---

## 2.14 Riesgos del Sistema

| ID | Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|---|
| R-01 | Grafo OSM desactualizado — nuevas vías o cierres no reflejados | Media | Alto | Actualización mensual programada del grafo OSM; caché con fecha de vigencia visible en el panel de administración |
| R-02 | Datos de tráfico hardcodeados — factor_hora estático no refleja condiciones reales | Alta | Medio | Feature flag para futura integración con datos de tráfico en tiempo real (API externa); documentado en roadmap |
| R-03 | MEXCLP fuera de v1 — posible despacho que deja zona sin cobertura | Media | Alto | Documentado como exclusión consciente de v1 (ver Daskin 1983 para el modelo MEXCLP); sistema alerta cuando la única unidad de una zona geográfica es despachada |
| R-04 | Confusión de unidades — km vs. m, segundos vs. minutos en cálculo interno | Baja | Muy alto | Tipos fuertes en todo el modelo de datos (longitud siempre en metros, tiempo siempre en segundos); tests unitarios de conversión explícitos |
| R-05 | Caída del backend durante triaje activo | Media | Alto | Persistencia local del estado del árbol de triaje en el navegador (localStorage); reenvío automático al recuperar la conexión |
| R-06 | Coordenadas GPS imprecisas — señal urbana degradada | Alta | Medio | Snap al nodo OSM más cercano; alerta visual si snap > 500 m con confirmación obligatoria del operador |
| R-07 | Mismatch crítico por saturación — única opción es Básica para Echo | Baja | Muy alto | Alerta visual roja "Despacho sub-óptimo crítico"; campo `despacho_suboptimo: true` en log; notificación a administrador de flota |
| R-08 | Sesgo del árbol MPDS-subset — no es el protocolo MPDS oficial certificado | Alta (por diseño) | Medio | Documentado explícitamente en la interfaz y en este SRS como "subset inspirado en MPDS, sin certificación clínica"; fuera de alcance para uso en sistemas reales |

---

## 2.15 Criterios de Aceptación

1. **Precisión de ruteo:** El tiempo de ruta calculado por A* coincide con el calculado por OSRM (oracle) con error ≤ 5% en el 95% de una muestra de 100 rutas de prueba dentro de la IV Región. (Verificado por CP-01.)

2. **Triaje correcto:** El árbol MPDS-subset asigna la categoría esperada en el 100% de los 12 incidentes del dataset de prueba. Ninguna categoría puede estar sub-asignada (Alpha en lugar de Echo es falla crítica).

3. **Idoneidad garantizada:** Echo y Delta nunca resultan asignados a una unidad Básica salvo que se active el flag de "Despacho sub-óptimo crítico" por saturación total; en ese caso el flag debe estar presente en el log. (Verificado por CP-05.)

4. **Re-despacho — comportamiento correcto en frontera:** CL-05 (progreso 60%) no genera propuesta de re-despacho; CL-06 (progreso 40%) sí genera propuesta con espera de confirmación. Ambos comportamientos verificados por CP-06 y CP-07.

5. **Performance:** El cálculo completo se ejecuta en ≤ 1 000 ms para flota de 50 unidades y en ≤ 300 ms para flota de 10 unidades, medidos en el servidor de prueba bajo carga nominal. (Verificado por CP-12.)

6. **Trazabilidad completa:** Cada despacho confirmado genera un log JSON con los campos obligatorios: id, timestamp ISO 8601, respuestas de triaje, categoría MPDS, costos desglosados por unidad evaluada, unidad seleccionada, ETA, ruta de nodos, flag de sub-óptimo y operador. (Verificado por CP-06 y CP-08.)

7. **Tolerancia a entradas inválidas:** Coordenadas fuera del rango IV Región son rechazadas antes de ejecutar cualquier cálculo, sin generar log de despacho. (Verificado por CP-09.)

8. **Roadmap MEXCLP:** La exclusión del modelo de cobertura MEXCLP de la v1 está documentada en este SRS (R-03), aprobada por los stakeholders del proyecto, y el sistema implementa la alerta de zona sin cobertura como mitigación mínima.

---

## 2.16 Validación del núcleo de cálculo (Java vs Python)

Requisito Transversal del proyecto del semestre (plantilla oficial GCS distribuida por el profesor el 2026-04-13). Define cómo se evidencia la equivalencia del núcleo de cálculo bajo dos implementaciones independientes.

- **RT-01.** El núcleo de cálculo (árbol de triaje MPDS-subset + algoritmo A* + función de costo multiobjetivo) deberá ser implementado o simulado en ambos lenguajes: Python y Java.
- **RT-02.** Los resultados de ambas implementaciones deberán ser equivalentes dentro de un margen de tolerancia definido.
- **RT-03.** Se deberá documentar cualquier diferencia detectada entre las dos implementaciones.
- **RT-04.** Se deberá justificar cuál implementación se considera más adecuada para el contexto del proyecto.

### Alcance del núcleo dual

**Implementado en ambos lenguajes**:

- Árbol de triaje MPDS-subset (sec. 2.6-A).
- Algoritmo A* con heurística Haversine sobre el grafo OSM cargado de GraphML.
- Función de costo `α·T_viaje + β·Penalización_Idoneidad` y selección por `argmin`.

**Implementado solo en Python** (no duplicado en Java por economía de esfuerzo, justificable como simulación según RT-01):

- Política de re-despacho (RF-08).
- Persistencia y log inmutable (RF-06, RN-03, RN-07).
- API REST y CLI.
- Generación del grafo OSM desde OSMnx (Java consume el GraphML pre-generado).
- Validación de rango, autenticación, log de auditoría.

### Tolerancias de equivalencia (RT-02)

| Campo de salida | Tolerancia | Justificación |
|---|---|---|
| `categoria_mpds` | exact match | Discreto; no admite tolerancia |
| `unidad_seleccionada.id` | exact match | Desempate determinista por ID lexicográfico (CL-02) |
| `despacho_suboptimo` (bool) | exact match | Discreto |
| `eta_segundos` | ±5% | Diferencias por orden de relajación A* con empates de costo |
| `costo.T_viaje` | ±5% | Idem |
| `costo.total` | ±5% | Idem |
| `ruta` (lista de nodos) | origen/destino idéntico, longitud ±10% | A* puede recorrer caminos alternativos de costo equivalente |

La comparación se ejecuta sobre los 12 incidentes del dataset (sec. 2.12) y produce un reporte automático versionado en el repositorio.

### Diferencias previsibles (RT-03)

Las diferencias documentables surgen de tres fuentes técnicas conocidas:

1. **Aritmética de coma flotante.** Python (`float`) y Java (`double`) usan IEEE 754 double precision, pero el orden de las operaciones puede producir diferencias en los bits menos significativos. Mitigación: tolerancia ±5% en numéricos.
2. **Orden de relajación A*.** Misma heurística Haversine y mismo costo de arista en ambas implementaciones, pero la cola de prioridad (Python `heapq` vs Java `PriorityQueue`) decide distinto frente a nodos con costo idéntico. Mitigación: desempate determinista por ID de nodo cuando aparece empate exacto.
3. **Parseo de GraphML.** Ambos cargan el mismo archivo `coquimbo.graphml`, pero el orden de aristas devuelto por el parser puede variar. Mitigación: test de integridad inicial verifica que el conjunto de aristas cargadas es idéntico en ambos lados.

### Justificación de adecuación (RT-04)

Para el contexto del proyecto, la implementación Python es la **referencia primaria**:

- **Ecosistema GIS.** `OSMnx` no tiene equivalente en Java; reescribir la ingesta OSM en Java agregaría 4–6 semanas sin valor académico.
- **Plazo académico.** Python permite mayor cobertura funcional (API, persistencia, simulador) en el tiempo disponible.
- **Literatura citada.** Boeing (2017) y Barrington-Leigh & Millard-Ball (2015) usan el mismo stack Python.

La implementación Java aporta:

- **Validación cruzada del núcleo crítico** (RT-01..RT-03).
- **Tipos estáticos en compile-time**, útiles para detectar inconsistencias del modelo de dominio.
- **Performance benchmarking** contra JVM caliente (informe final).

**Veredicto**: Python como implementación primaria del sistema; Java como validador del núcleo. La partición refleja el ecosistema disponible (Python tiene OSMnx; Java tiene JGraphT) y se documenta en la decisión arquitectónica del proyecto.
