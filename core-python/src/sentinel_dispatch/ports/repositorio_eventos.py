"""Port :class:`RepositorioEventos` (Ports & Adapters — ADR-0006, ADR-0007).

Define la interfaz de persistencia append-only del log de eventos del
sistema. Cumple **RN-03** (log inmutable) y **RN-07** (append-only)
estructuralmente: el Protocol no expone métodos ``update`` ni
``delete``; los adapters concretos respetan esa garantía sin necesidad
de triggers SQL.

Implementación de referencia: :class:`JsonlRepositorioEventos`
(``adapters/repositorio_jsonl.py``, ADR-0018). Migración futura a
``SqlRepositorioEventos`` si se dispara alguno de los criterios de
ADR-0007 §"Plan de migración".

Modelo de datos (ver ``docs/data-model.md``):

- :class:`EventoLog` value object inmutable que el repositorio persiste.
- :class:`TipoEvento` taxonomía cerrada de los 7 tipos del modelo.
- :exc:`EventoDuplicadoError` señaliza intento de re-escribir un
  ``evento_id`` ya presente (idempotencia de :meth:`append`).
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from collections.abc import Iterator


class TipoEvento(StrEnum):
    """Taxonomía cerrada de eventos del log (``docs/data-model.md``).

    Los valores se persisten literalmente en el JSONL. **No renombrar**
    sin actualizar ADR-0007, ADR-0018 y los logs históricos (los
    archivos persistidos no se migran automáticamente).

    Productores activos en v1 (H4):

    - :attr:`DESPACHO_CREADO`: emitido por el orquestador tras un
      ``despachar(...)`` exitoso o saturado (el "intento de despacho"
      se persiste para auditoría aunque no haya unidad elegida).

    Sin productor en v1 (declarados para que la taxonomía cierre el
    modelo de datos, productores se agregan en H5 si se aborda RF-08):

    - :attr:`DESPACHO_CANCELADO`, :attr:`DESPACHO_FINALIZADO`,
      :attr:`REDESPACHO_PROPUESTO`, :attr:`REDESPACHO_CONFIRMADO`,
      :attr:`REDESPACHO_RECHAZADO`, :attr:`UNIDAD_ACTUALIZADA`.
    """

    DESPACHO_CREADO = "despacho_creado"
    DESPACHO_CANCELADO = "despacho_cancelado"
    DESPACHO_FINALIZADO = "despacho_finalizado"
    REDESPACHO_PROPUESTO = "redespacho_propuesto"
    REDESPACHO_CONFIRMADO = "redespacho_confirmado"
    REDESPACHO_RECHAZADO = "redespacho_rechazado"
    UNIDAD_ACTUALIZADA = "unidad_actualizada"


class EventoLog(BaseModel):
    """Value object inmutable que representa un evento del log JSONL.

    Schema congelado en **ADR-0018**. Cualquier cambio futuro de campos
    requiere ADR nuevo y migración de logs históricos (script ad-hoc).

    Reglas de serialización:

    - ``model_dump_json()`` produce JSON sin BOM, sin indentación, una
      sola línea — apto para escritura JSONL.
    - ``extra="forbid"`` rechaza campos desconocidos en lectura para
      detectar drift de schema explícitamente.
    - ``frozen=True`` hace al modelo inmutable tras construcción y
      hasheable (permite usarlo en sets para el dedupe por ``evento_id``).
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    evento_id: str = Field(
        ...,
        description=(
            "Identificador opaco único monotónico. Convención: "
            "`EVT-<YYYYMMDDTHHMMSS>-<seq04>`. Generador en el adapter."
        ),
        min_length=1,
    )
    timestamp_iso: str = Field(
        ...,
        description="Timestamp del evento en ISO 8601 UTC con sufijo Z.",
        min_length=20,
    )
    tipo: TipoEvento
    despacho_id: str | None = Field(
        default=None,
        description="ID del despacho asociado, si aplica al tipo de evento.",
    )
    incidente_id: str | None = Field(
        default=None,
        description="ID del incidente asociado, si aplica al tipo de evento.",
    )
    operador: str = Field(
        default="samu_sistema",
        description=(
            "Identificador del operador o sistema que originó el evento. "
            "En v1 sin autenticación: `samu_sistema` por default."
        ),
        min_length=1,
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Subobjeto con datos específicos del tipo de evento. Para "
            "`despacho_creado` el shape coincide con el schema RT-02 "
            "de ADR-0017 (reutiliza `serializar_resultado_despacho`)."
        ),
    )


class EventoDuplicadoError(ValueError):
    """Levantada por :meth:`RepositorioEventos.append` ante un ``evento_id`` ya presente.

    Garantiza idempotencia: dos llamadas con el mismo ``evento_id`` no
    duplican filas en el log (la segunda falla en vez de re-escribir).
    """


@runtime_checkable
class RepositorioEventos(Protocol):
    """Port de persistencia append-only del log de eventos.

    **No expone ``update`` ni ``delete``** por diseño (RN-03, RN-07).
    Cualquier corrección requiere emitir un evento posterior, no
    modificar uno previo.

    Marcado ``@runtime_checkable`` para permitir validación estructural
    en tests (``isinstance(adapter, RepositorioEventos)``).
    """

    def append(self, evento: EventoLog) -> None:
        """Persiste un evento al final del log. Idempotente por ``evento_id``.

        Raises:
            EventoDuplicadoError: si ``evento.evento_id`` ya existe en
                el log.
        """
        ...

    def leer_todos(self) -> Iterator[EventoLog]:
        """Itera todos los eventos en orden de escritura.

        El stream se cierra al finalizar la iteración. Para grandes
        volúmenes prefiérase :meth:`filtrar` con criterios para evitar
        materializar todo en memoria.
        """
        ...

    def filtrar(
        self,
        *,
        despacho_id: str | None = None,
        tipo: TipoEvento | None = None,
    ) -> Iterator[EventoLog]:
        """Itera los eventos que cumplen los criterios provistos.

        Los criterios se combinan con AND lógico. ``None`` significa
        "no filtrar por ese campo". Implementaciones JSONL hacen
        scan lineal; SQL usaría índices.
        """
        ...
