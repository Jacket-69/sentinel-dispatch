"""Implementación JSONL append-only de :class:`RepositorioEventos` (ADR-0007, ADR-0018).

Persiste eventos del sistema en un archivo JSONL (una línea = un objeto
JSON validado por Pydantic). Cumple **RN-03** y **RN-07** por construcción:
el adapter sólo expone :meth:`append` + lecturas, no hay API de
actualización ni borrado.

Concurrencia (v1): un solo operador SAMU según ADR-0007. **No se usa
lock externo** (``fcntl`` o similar) porque no hay escritores concurrentes
reales. Si Fase 5 (simulación) llegara a escribir desde múltiples
threads, el adapter deberá envolverse en :class:`threading.Lock` o
similar; el cambio es trivial y se documentará en ADR-0018 §"Plan de
migración" cuando se gatille.

Idempotencia: :meth:`append` mantiene en memoria el set de ``evento_id``
ya vistos (cargados desde disco al construir el adapter) y rechaza
duplicados con :exc:`EventoDuplicadoError`. Esto previene escribir dos
veces el mismo evento ante un reintento del caller.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sentinel_dispatch.ports.repositorio_eventos import (
    EventoDuplicadoError,
    EventoLog,
    TipoEvento,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


_log = logging.getLogger(__name__)


class JsonlRepositorioEventos:
    """Adapter JSONL append-only del port :class:`RepositorioEventos`.

    Args:
        path: ruta absoluta al archivo JSONL. Se crea (con ``parents``)
            si no existe en la primera llamada a :meth:`append`. Si ya
            existe, los ``evento_id`` previos se cargan en memoria para
            preservar la idempotencia.
    """

    _path: Path
    _evento_ids_vistos: set[str]
    _secuencia: int

    def __init__(self, path: Path) -> None:
        self._path = path
        self._evento_ids_vistos = set()
        self._secuencia = 0
        if path.exists():
            for evento in self._iter_archivo():
                self._evento_ids_vistos.add(evento.evento_id)

    @property
    def path(self) -> Path:
        """Path absoluto del archivo JSONL respaldado por este adapter."""
        return self._path

    # ------------------------------------------------------------------
    # Port: append + lecturas
    # ------------------------------------------------------------------

    def append(self, evento: EventoLog) -> None:
        """Persiste un evento al final del JSONL. Idempotente por ``evento_id``.

        Raises:
            EventoDuplicadoError: si ``evento.evento_id`` ya está
                presente en el log (sea por carga al construir el
                adapter o por un ``append`` previo en esta misma
                instancia).
        """
        if evento.evento_id in self._evento_ids_vistos:
            raise EventoDuplicadoError(
                f"evento_id duplicado: {evento.evento_id!r} ya existe en el log."
            )
        self._path.parent.mkdir(parents=True, exist_ok=True)
        linea = evento.model_dump_json()
        with self._path.open("a", encoding="utf-8") as f:
            f.write(linea + "\n")
        self._evento_ids_vistos.add(evento.evento_id)
        _log.debug("evento_log.append", extra={"evento_id": evento.evento_id, "tipo": evento.tipo})

    def leer_todos(self) -> Iterator[EventoLog]:
        """Itera todos los eventos del log en orden de escritura."""
        yield from self._iter_archivo()

    def filtrar(
        self,
        *,
        despacho_id: str | None = None,
        tipo: TipoEvento | None = None,
    ) -> Iterator[EventoLog]:
        """Itera los eventos que matchean los criterios (AND lógico).

        ``None`` en un criterio significa "no filtrar por ese campo".
        Implementación: scan lineal. Suficiente para el volumen del
        proyecto (~30-50 eventos por simulación, ADR-0007).
        """
        for evento in self._iter_archivo():
            if despacho_id is not None and evento.despacho_id != despacho_id:
                continue
            if tipo is not None and evento.tipo is not tipo:
                continue
            yield evento

    # ------------------------------------------------------------------
    # Helpers de generación de evento_id (no parte del port)
    # ------------------------------------------------------------------

    def generar_evento_id(self, *, base_ts: datetime | None = None) -> str:
        """Genera un ``evento_id`` único monotónico para esta instancia.

        Formato: ``EVT-<YYYYMMDDTHHMMSS>-<seq04>``. La secuencia es
        in-memory por instancia del adapter; reabrir el log resetea la
        secuencia pero los ``evento_id`` ya escritos siguen siendo únicos
        gracias al timestamp del lado izquierdo del id.

        Args:
            base_ts: opcional; permite inyectar un timestamp determinístico
                en tests. Si es ``None`` se usa ``datetime.now(UTC)``.

        Returns:
            String con formato ``EVT-YYYYMMDDTHHMMSS-NNNN`` único.
        """
        ts = base_ts if base_ts is not None else datetime.now(UTC)
        self._secuencia += 1
        return f"EVT-{ts.strftime('%Y%m%dT%H%M%S')}-{self._secuencia:04d}"

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _iter_archivo(self) -> Iterator[EventoLog]:
        """Iterador interno: streaming del JSONL en disco."""
        if not self._path.exists():
            return
        with self._path.open("r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line:
                    continue
                yield EventoLog.model_validate_json(line)
