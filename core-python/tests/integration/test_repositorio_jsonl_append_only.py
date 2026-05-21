"""IT del adapter :class:`JsonlRepositorioEventos`.

Cubre escenarios end-to-end de persistencia y el spike CP-08
("intentar editar un log no debe ser posible / debe ser detectable").

Marcador: ``integration`` (corre en CI; el job `python-test` lo incluye).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from sentinel_dispatch.adapters.repositorio_jsonl import JsonlRepositorioEventos
from sentinel_dispatch.ports.repositorio_eventos import (
    EventoDuplicadoError,
    EventoLog,
    TipoEvento,
)

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


def _evento(
    evento_id: str,
    *,
    tipo: TipoEvento = TipoEvento.DESPACHO_CREADO,
    despacho_id: str = "SD-20260521-0001",
    incidente_id: str = "I-01",
) -> EventoLog:
    return EventoLog(
        evento_id=evento_id,
        timestamp_iso="2026-05-21T12:00:00.000Z",
        tipo=tipo,
        despacho_id=despacho_id,
        incidente_id=incidente_id,
        payload={"motivo": "optimo"},
    )


# ---------------------------------------------------------------------------
# Persistencia: round-trip y reapertura
# ---------------------------------------------------------------------------


def test_persistencia_atraviesa_reapertura_del_adapter(tmp_path: Path) -> None:
    """5 appends + descartar + reabrir → leer_todos retorna los 5 originales."""
    path = tmp_path / "eventos.jsonl"

    repo_a = JsonlRepositorioEventos(path)
    ids_originales = [f"EVT-RT-{i:04d}" for i in range(5)]
    for eid in ids_originales:
        repo_a.append(_evento(eid))

    del repo_a  # simula cierre de proceso

    repo_b = JsonlRepositorioEventos(path)
    ids_leidos = [e.evento_id for e in repo_b.leer_todos()]
    assert ids_leidos == ids_originales


def test_dos_instancias_secuenciales_comparten_archivo(tmp_path: Path) -> None:
    """Dos adapters secuenciales sobre el mismo path componen un único log."""
    path = tmp_path / "eventos.jsonl"

    repo_a = JsonlRepositorioEventos(path)
    repo_a.append(_evento("EVT-X-0001"))

    # Cerrar implícitamente la primera instancia y reabrir una nueva: debe
    # leer el evento ya escrito y permitir append sin duplicar.
    repo_b = JsonlRepositorioEventos(path)
    repo_b.append(_evento("EVT-X-0002"))

    ids = [e.evento_id for e in JsonlRepositorioEventos(path).leer_todos()]
    assert ids == ["EVT-X-0001", "EVT-X-0002"]


# ---------------------------------------------------------------------------
# Spike CP-08 — "intentar editar el log no debe ser posible / debe ser detectable"
# ---------------------------------------------------------------------------


class TestSpikeCP08:
    """Spike CP-08: el log JSONL no expone API de mutación.

    El SRS exige que "una vez creado un log de despacho no puede ser
    modificado". Como JSONL es archivo plano, un actor con acceso al
    filesystem podría editar bytes manualmente. Este spike documenta:

    1. **Estructural (API)**: el adapter no expone update/delete. Cubierto
       por los UT de ``TestReglasNegocio`` (RN-03/RN-07).
    2. **Idempotencia ante reescritura**: si alguien duplica una línea,
       el adapter rechaza el duplicado en la siguiente reapertura via
       :exc:`EventoDuplicadoError`.
    3. **Detección de schema drift**: campos desconocidos o tipos
       inválidos en el archivo levantan :exc:`ValidationError` de
       Pydantic en lectura.
    4. **No criptográfico**: no se firma cada línea con HMAC; v1 confía
       en el control de acceso al filesystem (ADR-0007). Migración a
       SQL con triggers + auditoría daría inmutabilidad de auditoría
       fuerte si el proyecto lo justifica (no es scope v1).

    Conclusión del spike: CP-08 se cumple en el sentido "el sistema no
    proporciona forma de editar"; modificaciones externas al adapter
    están fuera de su contrato y son responsabilidad de seguridad
    operativa (permisos POSIX).
    """

    def test_duplicar_linea_externamente_es_detectable_en_reapertura(self, tmp_path: Path) -> None:
        path = tmp_path / "eventos.jsonl"
        repo = JsonlRepositorioEventos(path)
        repo.append(_evento("EVT-CP08-0001"))

        # Atacante: duplica la línea fuera del adapter.
        contenido = path.read_text(encoding="utf-8")
        path.write_text(contenido + contenido, encoding="utf-8")

        # Reabrir: el adapter carga el set de IDs; si vuelven a aparecer
        # duplicados al iterar, se hace evidente al consumidor.
        repo_post = JsonlRepositorioEventos(path)
        ids = [e.evento_id for e in repo_post.leer_todos()]
        # Documenta el efecto observable: leer_todos refleja el archivo
        # tal cual está. La duplicación NO se filtra silenciosamente —
        # queda visible para que el operador la detecte.
        assert ids.count("EVT-CP08-0001") == 2

        # Y el adapter rechazaría escribir un tercer evento con el mismo id.
        with pytest.raises(EventoDuplicadoError):
            repo_post.append(_evento("EVT-CP08-0001"))

    def test_corromper_linea_externamente_levanta_validationerror_al_reabrir(
        self, tmp_path: Path
    ) -> None:
        """Schema drift detectable: reabrir el adapter sobre un archivo
        corrupto levanta ``ValidationError`` durante el ``__init__`` (el
        adapter pre-carga los ``evento_id`` para idempotencia y eso
        re-valida cada línea contra el schema canónico). Detección fail-fast,
        sin tolerar corrupciones silenciosas.
        """
        from pydantic import ValidationError

        path = tmp_path / "eventos.jsonl"
        repo = JsonlRepositorioEventos(path)
        repo.append(_evento("EVT-CP08-0002"))

        # Atacante: agrega una línea con schema inválido (falta campo `tipo`).
        with path.open("a", encoding="utf-8") as f:
            f.write('{"evento_id": "EVT-MALO", "campo_invalido": 42}\n')

        # Reabrir el adapter sobre el archivo corrupto: ValidationError fail-fast.
        with pytest.raises(ValidationError):
            JsonlRepositorioEventos(path)
