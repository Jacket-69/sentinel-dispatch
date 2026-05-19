---
adr: 0012
title: Ubicación del validador de coordenadas IV Región — dominio vs adapter
status: accepted
date: 2026-05-19
deciders: Benjamín López
tags: [adr, dominio, validacion, srs, rf01, rn01, hexagonal]
---

# ADR 0012 — Ubicación del validador de coordenadas IV Región

## Contexto

El SRS exige validar que las coordenadas de un incidente caigan dentro
del bbox normativo de la IV Región de Coquimbo
(`lat ∈ [-30.5, -29.5]`, `lon ∈ [-71.7, -70.5]`) antes de ejecutar
cualquier cálculo aguas abajo. Las referencias normativas son:

- **RF-01** (SRS sec. 2.5 / matriz §1): "El sistema permite ingresar las
  coordenadas del incidente con validación de rango en tiempo real".
- **RN-01** (SRS sec. 2.6): "Coordenadas fuera del rango de la IV Región
  son rechazadas con mensaje de error descriptivo antes de ejecutar
  cualquier cálculo".
- **CP-09** (SRS sec. 2.13): `lat=-31.200000, lon=-71.300000` debe
  rechazarse con mensaje "Coordenadas fuera del área de cobertura (IV
  Región)"; no se ejecuta A* ni cálculo de costo; no se genera log de
  despacho.

Durante H1 y H2 la validación se introdujo de forma **localizada en el
adapter** `OsmnxGrafoVial.nodo_mas_cercano` (`adapters/grafo_osmnx.py`),
con constantes privadas `_LAT_MIN`, `_LAT_MAX`, `_LON_MIN`, `_LON_MAX`
y una excepción `NodoFueraDeRangoError` definida en
`domain/routing/tipos.py`. Esa decisión cubrió la necesidad de proteger
el snap (RN-09) pero dejó un boquete:

1. La validación se ejecuta **dentro** del adapter, cuando una
   coordenada inválida ya cruzó toda la frontera del sistema. CP-09 exige
   rechazo **antes de cualquier cálculo**, lo que arquitectónicamente
   significa "en el borde", no "en el snap".
2. El mensaje del adapter (`"Coordenadas (..) fuera del area de cobertura
   IV Region (lat in [..], lon in [..])."`) no coincide textualmente con
   el mensaje normativo del CP-09 ("Coordenadas fuera del área de
   cobertura (IV Región).").
3. Si en el futuro se agregaran interfaces que no pasan por el snap
   (p. ej. un endpoint que solo registra incidentes sin despacharlos
   todavía), la validación se omitiría silenciosamente.

ADR-0006 (Ports & Adapters) establece que las reglas de negocio viven en
`domain/`. La validación de rango geográfico es una regla de negocio
(RN-01), no una preocupación del adapter OSMnx — el adapter solo "sabe"
porque el snap necesitaba defensa.

## Decisión

1. **Mover la validación al dominio**, en un nuevo paquete
   `domain/incidente/` (espacio reservado para entidades y reglas de
   incidentes, anticipando H3). Concretamente:

   - `domain/incidente/validacion.py` exporta:
     - Constantes `LAT_MIN_IV_REGION`, `LAT_MAX_IV_REGION`,
       `LON_MIN_IV_REGION`, `LON_MAX_IV_REGION`.
     - Excepción `CoordenadasFueraDeRangoError(ValueError)` con
       atributos `lat`, `lon` y mensaje fijo `MENSAJE_FUERA_DE_RANGO`
       igual al textual del CP-09.
     - Función pura `validar_coordenadas_iv_region(lat, lon) -> None`
       que verifica finitud (`isfinite`) y luego rango cerrado.

2. **Aplicar la validación en el borde**, no solo en el adapter:

   - `interfaces/api/main.py` expone
     `POST /v1/incidentes/validar-coordenadas`, que devuelve **422**
     con `detail.mensaje == MENSAJE_FUERA_DE_RANGO` cuando la coordenada
     cae fuera del bbox, y **200** en otro caso.
   - El adapter `OsmnxGrafoVial.nodo_mas_cercano` sigue invocando la
     misma función como **segunda barrera** (defense in depth), pero
     ahora atrapa `CoordenadasFueraDeRangoError` y la re-lanza como
     `NodoFueraDeRangoError` para no romper el contrato de excepciones
     existente del adapter.

3. **Jerarquía de excepciones**: `NodoFueraDeRangoError` pasa a ser
   subclase de `CoordenadasFueraDeRangoError`. Esto permite que los
   handlers del borde (API, futura CLI de dispatch) capturen el padre y
   los call-sites históricos del adapter sigan capturando el hijo. El
   constructor del hijo conserva la firma `(mensaje, *, lat, lon)` para
   absorber el caso degenerado "grafo sin nodos", donde `lat`/`lon` no
   aplican.

## Consecuencias

**Positivas:**

- CP-09 se prueba a nivel HTTP (no solo a nivel de adapter), eliminando
  el boquete original. El test de integración
  `test_api_validacion_coordenadas.py::TestApiValidacionReglaDeNegocio`
  cubre el caso textual.
- El mensaje normativo del CP-09 vive en un solo lugar
  (`MENSAJE_FUERA_DE_RANGO`), garantizando consistencia entre adapter y
  API.
- El dominio `incidente` queda preparado para H3 (dispatch): bastará
  agregar entidades `Incidente`, `Unidad`, etc. en el mismo paquete.
- La validación es ahora una función pura sin dependencias de
  framework; reutilizable desde la CLI futura sin acoplamiento.

**Negativas / costos:**

- Doble validación: la coordenada se verifica en el borde (API) y otra
  vez en el snap del adapter. El costo es despreciable (cuatro
  comparaciones por llamada) y vale como red de seguridad para
  call-sites internos.
- Los tests del adapter
  (`test_grafo_osmnx_snap.py::TestSnapError`) cambiaron su `match` de
  `"fuera del area de cobertura"` (sin tilde, mensaje viejo) a
  `"cobertura"` para tolerar el mensaje normativo unificado con tildes.

**Neutrales:**

- `NodoFueraDeRangoError` se mantiene como nombre porque los tests
  existentes y la documentación interna ya lo referencian; ahora es un
  alias semántico para "RN-01 disparado dentro del snap".

## Trazabilidad

- RF-01 → `interfaces/api/main.py::validar_coordenadas` + `domain/incidente/validacion.py::validar_coordenadas_iv_region`.
- RN-01 → `domain/incidente/validacion.py::validar_coordenadas_iv_region`.
- CP-09 → `tests/unit/domain/incidente/test_validacion_coordenadas.py::TestValidacionReglaDeNegocio::test_cp09_textual_lat_minus_31_2_lon_minus_71_3` + `tests/integration/test_api_validacion_coordenadas.py::TestApiValidacionReglaDeNegocio::test_cp09_lat_minus_31_2_lon_minus_71_3_devuelve_422_con_mensaje`.

## Referencias

- SRS secciones 2.5 (RF-01), 2.6 (RN-01), 2.13 (CP-09).
- ADR-0006 — Ports & Adapters liviano.
- ADR-0010 — Routing A* + estrategia de validación con OSRM oracle.
- Matriz de trazabilidad `docs/quality/trazabilidad.md` filas RF-01, RN-01, CP-09.
