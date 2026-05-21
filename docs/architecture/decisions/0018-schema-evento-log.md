---
adr: 0018
title: Schema del evento_log JSONL (RF-06, RN-03, RN-07)
status: accepted
date: 2026-05-21
deciders: Benjamin López
tags: [adr, persistencia, schema, log, h4]
---

# ADR 0018 — Schema del evento_log JSONL

## Contexto

[ADR-0007](0007-persistencia-jsonl.md) decidió que la persistencia v1 sería un archivo JSONL append-only (`data/eventos.jsonl`) gestionado por el port `RepositorioEventos`. Hasta ahora el port no existía en código y el contenido exacto de cada línea ("¿qué campos lleva un evento? ¿qué tipos? ¿cómo se identifica?") quedaba implícito.

Para cerrar **RF-06** (sistema persiste un log de despachos), **RN-03** (log inmutable) y **RN-07** (append-only) en H4 hay que (a) crear el port, (b) implementar el adapter JSONL real y (c) congelar el schema. Sin un schema congelado no se puede:

- Garantizar que el comparador externo (auditoría académica, futuro exportador RF-11) lea consistentemente los logs históricos.
- Detectar drift entre lo que persiste el sistema y lo que esperan los consumidores (parser CSV, simulación, etc.).
- Razonar sobre migración futura a SQL (ADR-0007 §"Plan de migración") sin un mapeo claro de columnas.

El [SRS sec. 2.13 CP-08](../../SRS.md) exige además que "una vez creado un log no puede ser modificado". El cumplimiento estructural (no exponer API de update/delete) se hereda de ADR-0007, pero hay que verificarlo empíricamente con un spike — esa es la convención `spike-before-CP` documentada en [CONTRIBUTING.md](../../../CONTRIBUTING.md) y aplicada antes en [ADR-0011](0011-reformulacion-criterio-it01.md).

## Decisión

Congelamos el siguiente schema como contrato del log canónico `data/eventos.jsonl`. Cualquier cambio futuro de campos requiere ADR nuevo + migración explícita de logs históricos.

### Schema canónico

```json
{
  "evento_id": "EVT-20260521T120000-0001",
  "timestamp_iso": "2026-05-21T12:00:00.000Z",
  "tipo": "despacho_creado",
  "despacho_id": "SD-20260521-0001",
  "incidente_id": "I-01",
  "operador": "samu_sistema",
  "payload": {
    "incidente_id": "I-01",
    "categoria_mpds": "Echo",
    "unidad_seleccionada": {"id": "U02"},
    "despacho_suboptimo": false,
    "motivo": "optimo",
    "eta_segundos": 187.42,
    "costo": {"T_viaje": 187.42, "penalizacion": 0.0, "total": 187.42},
    "ruta": ["123456", "234567"]
  }
}
```

### Justificación campo a campo

**`evento_id`** (str, required, min_length=1). Identificador opaco monotónico con formato `EVT-<YYYYMMDDTHHMMSS>-<seq04>`. El timestamp del prefijo garantiza ordenabilidad lexicográfica; la secuencia in-memory garantiza unicidad dentro de un mismo segundo. Si el adapter se reinicia, la secuencia reinicia desde 0001 — la unicidad la sigue dando el timestamp del prefijo (suficiente para v1 con 1 operador).

**`timestamp_iso`** (str ISO 8601, required). UTC con sufijo `Z`. Permite ordenar lexicográficamente sin parsear la cadena. Se prefiere string sobre `datetime` para que el JSONL sea independiente de la versión de Python que lo leyó.

**`tipo`** (str enum, required). Taxonomía cerrada de 7 valores derivados de [data-model.md](../../data-model.md): `despacho_creado`, `despacho_cancelado`, `despacho_finalizado`, `redespacho_propuesto`, `redespacho_confirmado`, `redespacho_rechazado`, `unidad_actualizada`. En H4 sólo se emite `despacho_creado` (incluso para saturación, ver §"Saturación" abajo); los demás quedan declarados sin productor activo hasta H5 si se aborda RF-08.

**`despacho_id`** (str | null, default null). Identificador del despacho asociado cuando aplica. Convención `SD-<YYYYMMDD>-<NNNN>` derivada del `incidente.timestamp_iso` y el `incidente.id` para que sea determinístico y reproducible en tests. `null` para tipos de evento que no atan a un despacho específico (e.g. `unidad_actualizada` independiente).

**`incidente_id`** (str | null, default null). FK al `Incidente` que originó el evento. `null` para eventos no atados a incidente.

**`operador`** (str, required, default `"samu_sistema"`). Identificador del actor que originó el evento. En v1 no hay autenticación (Tailscale + auth diferidos a F4 por ADR-0005), así que el default `samu_sistema` significa "evento producido por el sistema" (run-dataset, simulación). Cuando llegue F4, este campo absorbe el operador autenticado.

**`payload`** (dict, required). Subobjeto con datos específicos del tipo de evento. **Para `despacho_creado` el shape coincide bit-exacto con el schema RT-02 ([ADR-0017](0017-contrato-jsonl-validacion-dual.md))**: el adapter reutiliza `application.serializacion.serializar_resultado_despacho` para construirlo. Esta decisión evita drift entre los JSONL emitidos por incidente (RT-02) y los persistidos en el log canónico (RF-06). Si el schema RT-02 evoluciona, este ADR debe actualizarse en el mismo PR.

### Saturación se persiste como `despacho_creado`

En v1 NO se crea un tipo de evento `despacho_saturacion` aparte. La saturación se persiste como un `despacho_creado` con `payload.unidad_seleccionada=null` y `payload.motivo="saturacion"`. Razones:

- El modelo de datos (`docs/data-model.md`) sólo define 7 tipos; agregar uno requiere actualizar SRS, modelo y migración.
- Semánticamente, una saturación es un **intento de despacho** que vale la pena auditar (RF-06 §"persistir todos los despachos"). El consumidor del log distingue saturación por `payload.motivo`, no por `evento.tipo`.
- El comportamiento del adapter es uniforme: una línea por intento de despacho, exitoso o no.

### Inmutabilidad estructural (CP-08, RN-03, RN-07)

- El port `RepositorioEventos` **no expone** `update`, `delete`, `remove`. Test estructural (`test_rn03_rn07_protocol_no_expone_update_ni_delete`) lo verifica.
- El adapter `JsonlRepositorioEventos` **no implementa** esos métodos. Test estructural (`test_rn03_rn07_adapter_no_expone_update_ni_delete`) lo verifica.
- El método `append` rechaza re-escrituras con el mismo `evento_id` via `EventoDuplicadoError`. Garantiza idempotencia ante reintentos.
- El método `__init__` carga `evento_id` ya presentes desde disco para preservar la dedupe a través de procesos.

### Concurrencia

ADR-0007 explícitamente asume **un solo operador**. El adapter v1 **no usa lock externo** (`fcntl.flock`). Si Fase 5 (simulación) o un futuro F4 (Tailscale multi-usuario) requirieran escritura concurrente, el cambio es trivial:

```python
with self._path.open("a", encoding="utf-8") as f:
    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
    f.write(linea + "\n")
```

Se documentará en una versión `v2` de este ADR si llega el caso.

## Spike de viabilidad CP-08

Convención `spike-before-CP`: antes de comprometerse al criterio del SRS, se verifica empíricamente que sea alcanzable.

**Spike ejecutado**: `core-python/tests/integration/test_repositorio_jsonl_append_only.py::TestSpikeCP08`. Cubre:

1. **`test_duplicar_linea_externamente_es_detectable_en_reapertura`**: si un actor edita el archivo y duplica una línea, `leer_todos()` refleja el archivo tal cual está (no filtra silenciosamente), y `append` con el mismo `evento_id` levanta `EventoDuplicadoError`. **Conclusión**: el adapter no oculta la duplicación; el operador puede detectarla.
2. **`test_corromper_linea_externamente_levanta_validationerror_al_reabrir`**: si un actor agrega una línea con schema inválido, reabrir el adapter levanta `pydantic.ValidationError` durante `__init__` (fail-fast). **Conclusión**: schema drift es detectable inmediatamente.

**Resultado**: CP-08 se cumple en el sentido "el sistema no proporciona forma de editar el log". Modificaciones externas al adapter están fuera de su contrato; la inmutabilidad fuerte (anti-tampering criptográfico con HMAC por línea) está fuera de scope v1.

**Limitación documentada**: si un actor con acceso al filesystem reemplaza el archivo completo por uno fabricado, el adapter no puede detectarlo. Mitigación: control de acceso POSIX al directorio `data/`. Para auditoría clínica real se requeriría firma digital por línea + verificación al leer, lo que es propio de F4+ (no v1).

## Alternativas consideradas

### Schema plano (todos los campos a la raíz, sin `payload` anidado)

- **Pros**: más fácil de leer en herramientas tabulares (jq, csvkit).
- **Contras**: el shape varía por `tipo` de evento; con `payload` flat habría que agregar todos los campos posibles como nullable a la raíz, mezclando dominios. Cada nuevo tipo de evento ensucia la raíz con campos solo aplicables a otros.
- **Por qué se descartó**: la separación `metadata-de-evento / payload-específico` es semánticamente más limpia y se alinea con el patrón estándar de event sourcing.

### `evento_id` con ULID (lib externa)

- **Pros**: 26 chars, lexicográficamente ordenable, semántica probada en eventos distribuidos.
- **Contras**: dependencia nueva (`python-ulid` o similar, ~30 KB pero conceptualmente "una lib más"); para 1 operador y ~30-50 eventos por simulación, ULID es overkill.
- **Por qué se descartó**: el formato `EVT-<isoZ>-<seq04>` propio cumple las mismas garantías (unicidad, ordenabilidad) sin agregar dependencia. Si se migra a UI multi-usuario en F4, reconsiderar ULID.

### Persistir un tipo `despacho_saturacion` aparte

- **Pros**: explícito en la taxonomía; consumidores pueden filtrar saturación sin parsear `payload`.
- **Contras**: requiere actualizar SRS (sec. modelo), `data-model.md`, código del adapter, exportador. Mismo dato accesible via `payload.motivo=="saturacion"`.
- **Por qué se descartó**: agregar un tipo más solo para una distinción consultable es duplicación. Se reconsidera en H5 si RF-08 demanda granularidad de eventos.

### Hash criptográfico por línea (HMAC + clave secreta)

- **Pros**: detecta modificaciones externas; satisface auditoría clínica real.
- **Contras**: requiere gestión de claves, rotación, almacén de claves seguro. Inviable en proyecto académico sin infra de KMS.
- **Por qué se descartó**: fuera de scope v1; ADR-0007 explícitamente delega esto a F4+ con auth real.

## Consecuencias

### Positivas

- **RF-06, RN-03, RN-07 cumplidos** estructuralmente (no por convención, sino por API).
- **Test suite cubre los tres niveles**: estructural (port no expone update/delete), unitario (adapter rechaza duplicados, valida schema), spike (CP-08 modificación externa detectable).
- **Reutilización del payload con ADR-0017**: el log canónico embebe exactamente el dict que produce el comparador RT-02. Bit-exactitud garantizada por construcción.
- **Schema versionado**: cualquier cambio futuro pasa por ADR nuevo, no por commit silencioso.
- **Migración a SQL futura barata**: el `evento_id` es PK natural, `tipo` es CHECK constraint, `payload` es JSONB.

### Negativas / costo

- Cualquier cambio al schema RT-02 (ADR-0017) impacta este ADR. Mitigación: ambos schemas comparten `serializar_resultado_despacho`; cambios se detectan en CI por el job `compare` (12/12 OK) y por el test `test_flag_log_eventos_persiste_evento_por_incidente`.
- El `evento_id` con secuencia in-memory no es único entre procesos concurrentes. No es un problema en v1 (1 operador, 1 proceso a la vez), pero limita escalabilidad. Reconsiderar en F4.
- Pydantic strict + frozen tiene overhead de validación. Para 30-50 eventos por simulación es despreciable (~0.1 ms por evento medido en tests).

### Neutras

- El log se persiste por convención en `data/eventos.jsonl` (ignorado por git como estado runtime, ADR-0007 §"Cumplimiento"). El path es configurable por flag CLI (`--log-eventos`) o por construcción directa del adapter.
- El producto observable del sistema sigue siendo el JSONL RT-02 por incidente; el log canónico es **valor agregado opt-in** que activa el operador. El comportamiento por default (`run-dataset` sin `--log-eventos`) no cambia.

## Cumplimiento / verificación

- `core-python/src/sentinel_dispatch/ports/repositorio_eventos.py` define el port y los value objects.
- `core-python/src/sentinel_dispatch/adapters/repositorio_jsonl.py` implementa el adapter.
- `core-python/tests/unit/adapters/test_repositorio_jsonl.py` cubre las 4 clases de tests (Normal/Borde/Error/RN) — 16 tests.
- `core-python/tests/integration/test_repositorio_jsonl_append_only.py` cubre el spike CP-08 y reapertura entre procesos — 4 tests.
- `core-python/tests/unit/interfaces/cli/test_run_dataset_cmd.py::TestLogEventos` cubre la integración con el CLI — 2 tests.
- Matriz de trazabilidad (`docs/quality/trazabilidad.md`): RF-06, RN-03, RN-07 → ✅.

## Referencias

- [ADR-0006 — Ports & Adapters](0006-ports-and-adapters.md)
- [ADR-0007 — Persistencia JSONL append-only](0007-persistencia-jsonl.md)
- [ADR-0017 — Contrato JSONL para validación dual](0017-contrato-jsonl-validacion-dual.md)
- [SRS](../../SRS.md) — RF-06, RN-03, RN-07, CP-08.
- [data-model.md](../../data-model.md) — taxonomía de tipos de evento.
- [CONTRIBUTING.md](../../../CONTRIBUTING.md) — convención `spike-before-CP`.
