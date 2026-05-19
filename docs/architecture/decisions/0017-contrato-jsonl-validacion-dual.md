---
adr: 0017
title: Contrato JSONL para validacion dual Python-Java (RT-02)
status: accepted
date: 2026-05-19
deciders: Benjamin Lopez
tags: [adr, validacion, dual, jsonl, schema, rt]
---

# ADR 0017 — Contrato JSONL para validacion dual Python-Java (RT-02)

## Contexto

ADR-0008 establecio la estrategia de validacion dual: el nucleo de calculo
(triaje + routing + dispatch) se implementa en Python (primario) y en Java
(validacion), y los resultados se comparan con tolerancias definidas en cada
push a `main` mediante `tools/compare_outputs.py`.

El job `compare` del CI (`.github/workflows/ci.yml`) espera que ambos cores
produzcan archivos JSONL con un schema identico: un objeto JSON por incidente,
un archivo por incidente, nombrado `<incidente.id>.jsonl`. Sin este contrato
congelado en un ADR, cualquier cambio en Python o Java podria romper la
comparacion silenciosamente o crear drift entre implementaciones.

Hasta este PR, el contrato estaba implicito: el schema se inferia leyendo el
codigo del orquestador y del serializador. Esto es fragil para la defensa
academica (RT-03 pide documentar diferencias; no se puede documentar lo que
no esta especificado) y para el equipo Java que arranca en H3-J.

## Decision

Congelamos el schema JSONL producido por `sentinel run-dataset` como contrato
normativo. Cualquier cambio futuro al schema requiere una nueva version de
este ADR, actualizar el espejo Java y regenerar los fixtures de referencia.

### Schema — despacho exitoso (motivo in {OPTIMO, PENALIZADO, SUBOPTIMO_RN02})

```json
{"incidente_id":"I-01","categoria_mpds":"Alpha","unidad_seleccionada":{"id":"U02"},"despacho_suboptimo":false,"motivo":"optimo","eta_segundos":187.42,"costo":{"T_viaje":187.42,"penalizacion":0.0,"total":187.42},"ruta":[]}
```

### Schema — saturacion (motivo=SATURACION)

```json
{"incidente_id":"I-01","categoria_mpds":"Alpha","unidad_seleccionada":null,"despacho_suboptimo":false,"motivo":"saturacion","eta_segundos":null,"costo":null,"ruta":[]}
```

### Justificacion campo a campo

**`incidente_id`** (str): identificador opaco del evento. Clave de join entre
el JSONL de salida y el dataset de entrada. Tipo string para alinear con la
convencion `"I-01".."I-12"` del SRS sec. 2.11.

**`categoria_mpds`** (str, valor del enum): se serializa como el nombre
humano del enum ("Alpha", "Echo", etc.) en lugar de un entero porque (a) el
SRS y el profesor usan los nombres literales en todos los documentos, (b) un
entero requeriria una tabla de mapeo adicional en `compare_outputs.py` y en
el espejo Java, y (c) la comparacion con ground_truth del dataset de
aceptacion es directa sin conversion.

**`unidad_seleccionada`** (object|null): se serializa como `{"id": str}` y no
como el objeto `Unidad` completo para mantener el schema estable ante
cambios en los atributos de `Unidad` (patente, base, etc.) que no son
relevantes para la validacion RT-02. Solo el `id` entra en la comparacion
de equivalencia (ADR-0008 tabla de tolerancias: exact match).

**`despacho_suboptimo`** (bool): campo dedicado para que el log JSONL lo
persista bit-exacto sin re-derivarlo del `motivo` en cada lectura. Evita
la tentacion de inferir `motivo == "suboptimo_rn02"` en el comparador y
documenta la semantica de negocio explicitamente.

**`motivo`** (str, valor del enum): valor del `MotivoDespacho` en minusculas
(StrEnum Python serializa directamente el `.value`). Los valores posibles
son "optimo", "penalizado", "suboptimo_rn02" y "saturacion". El comparador
Java usara exact match sobre este campo.

**`eta_segundos`** (float|null): tiempo de viaje del A* en segundos (campo
`t_viaje_s` del `CostoDespacho`). Null en saturacion porque no hay unidad
elegida. Se serializa como decimal IEEE 754 double con `json.dumps` default
(sin notacion cientifica para valores tipicos 0..3600 s); la tolerancia
RT-02 es +-5% (ADR-0008).

**`costo`** (object|null): objeto anidado en lugar de campos planos porque
(a) agrupa semanticamente los tres escalares de la funcion de costo
(alpha*T_viaje + beta*Penalizacion), (b) es extensible sin romper el schema
(si se agrega un campo futuro como `factor_hora_aplicado`, va dentro del
objeto y no rompe parsers que no lo conocen), y (c) la comparacion de
tolerancia en `compare_outputs.py` puede iterar sobre las keys del objeto
en lugar de manejar nombres de campo planos ad-hoc.

**`ruta`** (array de str): lista de IDs de nodo de la ruta A*, serializados
como strings. Los IDs de nodo OSMnx son `int64`; algunos parsers JSON
(en particular, los que usan `long` en Java o `number` en JavaScript) no
manejan enteros mayores a 2^53 de forma uniforme. Serializar como string
garantiza exactitud en todos los lenguajes sin perdida. La ruta se emite
siempre como array (vacio en saturacion, no `null`) para que el comparador
pueda iterar sin verificar tipo.

**Nota sobre ruta vacia en v1**: el orquestador actual (`ResultadoDespacho`)
no expone la ruta de nodos — el A* la calcula internamente en
`_calcular_tiempos_viaje` pero no la persiste en el resultado. En esta
primera version del schema la ruta se emite como `[]`. La extension para
incluir la ruta real requiere modificar `ResultadoDespacho` y el orquestador,
lo que es scope de un PR separado con ADR propio.

### Reglas de serializacion

- Floats con `json.dumps` default (notacion decimal, no cientifica).
- Encoding UTF-8. Sin BOM. Sin indentacion. Sin trailing whitespace.
- Terminador de linea `\n` al final del archivo (convencion JSONL).
- Un objeto JSON por archivo, en una sola linea.
- Un archivo por incidente, nombrado `<incidente.id>.jsonl`.

## Alternativas consideradas

### Schema plano (sin objeto `costo` anidado)

- Pros: menos anidamiento, mas facil de leer en tabla.
- Contras: no extensible sin romper el schema; nombres de campo ambiguos
  (`total_segundos`, `penalizacion_segundos`); el comparador necesita
  conocer todos los nombres de campo individualmente.
- Por que se descarto: el objeto `costo` agrupa semanticamente y es la
  representacion natural de `CostoDespacho`.

### categoria_mpds como entero (0=Alpha, 4=Echo)

- Pros: compacto; mas facil de comparar en Java con enums ordinales.
- Contras: opaco para revision humana; el SRS y el profesor usan nombres
  literales en todos los documentos; requiere tabla de mapeo en Java y en
  `compare_outputs.py`.
- Por que se descarto: la legibilidad del schema prima en un proyecto
  academico que sera auditado por el profesor y evaluado en defensa.

### Todos los campos de Unidad en `unidad_seleccionada`

- Pros: el JSONL es autocontenido sin necesidad de join con unidades.json.
- Contras: el schema se acopla a los atributos de `Unidad`; cualquier cambio
  en `Unidad` (agregar campo, renombrar) rompe el schema y el espejo Java.
  Solo el `id` entra en la comparacion RT-02.
- Por que se descarto: minimo necesario para RT-02; el resto es auditoria,
  no validacion de equivalencia.

## Consecuencias

### Positivas

- Cualquier divergencia Java-Python queda detectable a nivel de byte por
  `tools/compare_outputs.py`.
- La activacion del job `compare` se reduce a quitar `if: false` en
  `.github/workflows/ci.yml` (H3-J-7).
- El comando `sentinel run-dataset` es reusable para regenerar fixtures de
  referencia para RT-02 sin modificar codigo.
- El equipo Java tiene un contrato escrito y ejemplos JSON para arrancar
  el espejo sin ambiguedad.

### Negativas / costo

- Cualquier cambio futuro en `ResultadoDespacho` (application/tipos.py)
  que afecte campos del schema requiere: (1) nueva version de este ADR,
  (2) actualizar `run_dataset_cmd.py`, (3) actualizar el espejo Java,
  (4) regenerar fixtures. Riesgo de drift; mitigacion: el job `compare`
  falla en cuanto los outputs divergen.
- El campo `ruta` se emite vacio en v1 (ver nota arriba); esto es una
  limitacion conocida documentada.

### Neutras

- El schema es un subconjunto de la informacion de `ResultadoDespacho`;
  no toda la informacion del orquestador se expone (candidatos, saturacion
  detallada).

## Cumplimiento / verificacion

- `core-python/tests/unit/interfaces/cli/test_run_dataset_cmd.py` verifica
  el schema en cada test Normal y RN.
- `tools/compare_outputs.py` aplica las tolerancias de ADR-0008 sobre
  este schema.
- El job `compare` del CI activa la comparacion en cada push (H3-J-7).

## Referencias

- [ADR-0008 — Validacion dual Java-Python](0008-validacion-dual-java-python.md)
- [ADR-0015 — Fallback RN-02 suboptimo](0015-fallback-rn02-suboptimo.md)
- `tools/compare_outputs.py`
- `.github/workflows/ci.yml` job `compare` (activar en H3-J-7 quitando `if: false`)
- `core-python/src/sentinel_dispatch/interfaces/cli/run_dataset_cmd.py`
