# Glosario del dominio

> Lenguaje del negocio que aparece en código, doc y conversaciones. Si introduces un término nuevo, agrégalo acá en el mismo PR.

## Triaje

| Término | Definición |
|---|---|
| **MPDS** | Medical Priority Dispatch System — protocolo internacional de triaje pre-hospitalario. Usamos un **subset** no certificado (ver R-08). |
| **MPDS-subset** | Implementación reducida del árbol MPDS con 7 preguntas; categoriza en Alpha/Bravo/Charlie/Delta/Echo. |
| **Categoría MPDS** | Resultado del árbol de triaje: `Alpha` (verde) → `Bravo` (amarillo) → `Charlie` (naranja) → `Delta` (rojo) → `Echo` (rojo crítico). |
| **Árbol de triaje** | Conjunto de preguntas binarias/categóricas cuyas respuestas determinan la `CategoriaMPDS`. |

## Flota

| Término | Definición |
|---|---|
| **Unidad** | Vehículo de emergencia con identificador único (`U01`–`U10`), patente, tipo y base. |
| **Tipo de unidad** | `Avanzada` (ALS, equipo y personal capacitados) o `Basica` (BLS, soporte vital básico). |
| **Estado de unidad** | `Disponible`, `EnRuta`, `EnEscena`, `Taller`. |
| **Base** | Coordenada (lat, lon) donde reside la unidad cuando `Disponible`. |

## Despacho

| Término | Definición |
|---|---|
| **Incidente** | Llamada de emergencia con coordenadas (lat, lon), respuestas de triaje y timestamp. ID `I-NNNN`. |
| **Despacho** | Asignación confirmada de una `Unidad` a un `Incidente`. ID `SD-YYYYMMDD-NNNN`. |
| **Re-despacho** | Reasignación de una `Unidad` `EnRuta` a un nuevo incidente de mayor categoría. Requiere confirmación humana (RN-06). |
| **Costo de despacho** | `Costo(u, i) = α·T_viaje + β·Penalización_Idoneidad` con `α=1.0`, `β=600 s` (sec. 2.6.C). |
| **Penalización_Idoneidad** | Adimensional. `0` si unidad apta; `1` si Charlie+Básica; `∞` si Echo/Delta+Básica. |
| **Saturación** | Estado del sistema cuando no hay unidades `Disponible`. |
| **Despacho sub-óptimo** | Asignación de Básica a Echo/Delta por saturación crítica; flag `despacho_suboptimo: true` en el log (RN-02). |

## Ruteo

| Término | Definición |
|---|---|
| **A*** | Algoritmo de búsqueda informada con heurística admisible. |
| **Heurística Haversine** | Distancia esférica origen-destino dividida por `v_max = 38.89 m/s`. Admisible → A* óptimo. |
| **Grafo OSM** | Grafo dirigido construido desde OpenStreetMap de la IV Región vía OSMnx. |
| **factor_hora** | Multiplicador `[0.60, 1.00]` que ajusta velocidad efectiva según rango horario (sec. 2.6.B). |
| **factor_sirena** | Multiplicador fijo `1.4`; reduce tiempo ~28.6% en zona urbana. |
| **velocidad_efectiva** | `maxspeed_OSM × (1000/3600) × factor_hora × factor_sirena` en m/s. |
| **peso(arista)** | `longitud_metros / velocidad_efectiva` en segundos. |
| **Snap al nodo OSM** | Cuando la coordenada del incidente no calza con un nodo del grafo, se asigna al más cercano con alerta si distancia >500 m (RN-09). |

## Operación

| Término | Definición |
|---|---|
| **ETA** | Estimated Time of Arrival, en segundos enteros. |
| **Log inmutable** | Registro JSON append-only de cada despacho (RN-03, RN-07). |
| **Operador** | Persona que opera la consola de despacho. |
| **Dataset de aceptación** | 12 incidentes del SRS sec. 2.12; tests `pytest -m dataset`. |
| **Oracle OSRM** | Motor de ruteo externo usado solo como benchmark de precisión para CP-01. |

## Magnitudes (convención de unidades)

| Magnitud | Unidad interna | Conversión |
|---|---|---|
| Distancia | metros (`int`/`float`) | km × 1000 |
| Tiempo | segundos (`int`) | min × 60; HH:MM solo en UI |
| Velocidad | m/s (`float`) | km/h × (1000/3600) |
| Coordenada | grados decimales (`float`, 6 decimales) | — |
