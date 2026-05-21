"""UT del adapter :class:`JsonlRepositorioEventos` (ADR-0007, ADR-0018).

Taxonomía: Normal / Borde / Error / RN.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from sentinel_dispatch.adapters.repositorio_jsonl import JsonlRepositorioEventos
from sentinel_dispatch.ports.repositorio_eventos import (
    EventoDuplicadoError,
    EventoLog,
    RepositorioEventos,
    TipoEvento,
)

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def repo(tmp_path: Path) -> JsonlRepositorioEventos:
    """Adapter sobre `tmp_path/eventos.jsonl` (archivo aún inexistente)."""
    return JsonlRepositorioEventos(tmp_path / "eventos.jsonl")


def _evento(
    evento_id: str = "EVT-20260521T120000-0001",
    *,
    tipo: TipoEvento = TipoEvento.DESPACHO_CREADO,
    despacho_id: str | None = "SD-20260521-0001",
    incidente_id: str | None = "I-01",
    payload: dict | None = None,
) -> EventoLog:
    """Factory de eventos con defaults seguros para tests Normales."""
    return EventoLog(
        evento_id=evento_id,
        timestamp_iso="2026-05-21T12:00:00.000Z",
        tipo=tipo,
        despacho_id=despacho_id,
        incidente_id=incidente_id,
        payload=payload or {"motivo": "optimo"},
    )


# ---------------------------------------------------------------------------
# Normal
# ---------------------------------------------------------------------------


class TestNormal:
    def test_append_un_evento_persiste_una_linea_jsonl(self, repo: JsonlRepositorioEventos) -> None:
        repo.append(_evento())
        contenido = repo.path.read_text(encoding="utf-8")
        lineas = [linea for linea in contenido.splitlines() if linea]
        assert len(lineas) == 1
        obj = json.loads(lineas[0])
        assert obj["evento_id"] == "EVT-20260521T120000-0001"
        assert obj["tipo"] == "despacho_creado"

    def test_leer_todos_devuelve_eventos_en_orden_de_escritura(
        self, repo: JsonlRepositorioEventos
    ) -> None:
        repo.append(_evento("EVT-20260521T120000-0001"))
        repo.append(_evento("EVT-20260521T120001-0002"))
        repo.append(_evento("EVT-20260521T120002-0003"))
        ids = [e.evento_id for e in repo.leer_todos()]
        assert ids == [
            "EVT-20260521T120000-0001",
            "EVT-20260521T120001-0002",
            "EVT-20260521T120002-0003",
        ]

    def test_filtrar_por_despacho_id_devuelve_solo_matches(
        self, repo: JsonlRepositorioEventos
    ) -> None:
        repo.append(_evento("EVT-A-0001", despacho_id="SD-A"))
        repo.append(_evento("EVT-A-0002", despacho_id="SD-A"))
        repo.append(_evento("EVT-B-0001", despacho_id="SD-B"))
        resultados = list(repo.filtrar(despacho_id="SD-A"))
        assert {e.evento_id for e in resultados} == {"EVT-A-0001", "EVT-A-0002"}

    def test_filtrar_por_tipo_devuelve_solo_matches(self, repo: JsonlRepositorioEventos) -> None:
        repo.append(_evento("EVT-0001", tipo=TipoEvento.DESPACHO_CREADO))
        repo.append(_evento("EVT-0002", tipo=TipoEvento.DESPACHO_FINALIZADO))
        repo.append(_evento("EVT-0003", tipo=TipoEvento.DESPACHO_CREADO))
        resultados = list(repo.filtrar(tipo=TipoEvento.DESPACHO_CREADO))
        assert {e.evento_id for e in resultados} == {"EVT-0001", "EVT-0003"}

    def test_filtrar_combinado_aplica_and(self, repo: JsonlRepositorioEventos) -> None:
        repo.append(_evento("EVT-0001", tipo=TipoEvento.DESPACHO_CREADO, despacho_id="SD-A"))
        repo.append(_evento("EVT-0002", tipo=TipoEvento.DESPACHO_FINALIZADO, despacho_id="SD-A"))
        repo.append(_evento("EVT-0003", tipo=TipoEvento.DESPACHO_CREADO, despacho_id="SD-B"))
        resultados = list(repo.filtrar(tipo=TipoEvento.DESPACHO_CREADO, despacho_id="SD-A"))
        assert [e.evento_id for e in resultados] == ["EVT-0001"]

    def test_implementa_protocol_repositorio_eventos(self, repo: JsonlRepositorioEventos) -> None:
        """isinstance check estructural con `Protocol`."""
        assert isinstance(repo, RepositorioEventos)


# ---------------------------------------------------------------------------
# Borde
# ---------------------------------------------------------------------------


class TestBorde:
    def test_archivo_inexistente_leer_todos_retorna_vacio(self, tmp_path: Path) -> None:
        repo = JsonlRepositorioEventos(tmp_path / "no-existe.jsonl")
        assert list(repo.leer_todos()) == []

    def test_archivo_existente_carga_evento_ids_para_idempotencia(self, tmp_path: Path) -> None:
        path = tmp_path / "eventos.jsonl"
        # Pre-escribir un evento "manualmente" simulando una sesión previa.
        evento_prev = _evento("EVT-20260520T120000-9999")
        path.write_text(evento_prev.model_dump_json() + "\n", encoding="utf-8")
        # Abrir adapter nuevo: debe cargar el id previo.
        repo = JsonlRepositorioEventos(path)
        # Si intento volver a agregar el mismo id, debe rechazar.
        with pytest.raises(EventoDuplicadoError):
            repo.append(_evento("EVT-20260520T120000-9999"))

    def test_payload_utf8_round_trip_exacto(self, repo: JsonlRepositorioEventos) -> None:
        """Caracteres especiales (ñ, tildes) sobreviven escritura y lectura."""
        repo.append(
            _evento(
                payload={
                    "motivo": "óptimo",
                    "operador_obs": "Recepción año mayúsculas con ñ",
                }
            )
        )
        leido = next(iter(repo.leer_todos()))
        assert leido.payload["motivo"] == "óptimo"
        assert leido.payload["operador_obs"] == "Recepción año mayúsculas con ñ"

    def test_archivo_con_linea_vacia_intermedia_se_ignora(self, tmp_path: Path) -> None:
        path = tmp_path / "eventos.jsonl"
        e1 = _evento("EVT-0001")
        e2 = _evento("EVT-0002")
        path.write_text(f"{e1.model_dump_json()}\n\n{e2.model_dump_json()}\n", encoding="utf-8")
        repo = JsonlRepositorioEventos(path)
        ids = [e.evento_id for e in repo.leer_todos()]
        assert ids == ["EVT-0001", "EVT-0002"]

    def test_generar_evento_id_es_unico_monotonico(self, repo: JsonlRepositorioEventos) -> None:
        ts = datetime(2026, 5, 21, 12, 0, 0, tzinfo=UTC)
        id1 = repo.generar_evento_id(base_ts=ts)
        id2 = repo.generar_evento_id(base_ts=ts)
        id3 = repo.generar_evento_id(base_ts=ts)
        assert id1 == "EVT-20260521T120000-0001"
        assert id2 == "EVT-20260521T120000-0002"
        assert id3 == "EVT-20260521T120000-0003"
        assert len({id1, id2, id3}) == 3


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------


class TestError:
    def test_append_evento_duplicado_levanta_eventoduplicadoerror(
        self, repo: JsonlRepositorioEventos
    ) -> None:
        repo.append(_evento("EVT-DUP-0001"))
        with pytest.raises(EventoDuplicadoError, match="evento_id duplicado"):
            repo.append(_evento("EVT-DUP-0001"))

    def test_pydantic_rechaza_extra_fields(self) -> None:
        """`EventoLog` configurado con `extra="forbid"` (drift detectable)."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            EventoLog.model_validate(
                {
                    "evento_id": "EVT-X",
                    "timestamp_iso": "2026-05-21T12:00:00.000Z",
                    "tipo": "despacho_creado",
                    "campo_inventado": "rompe schema",  # extra: prohibido
                }
            )


# ---------------------------------------------------------------------------
# Reglas de negocio (RN-03 / RN-07 estructural)
# ---------------------------------------------------------------------------


class TestReglasNegocio:
    def test_rn03_rn07_adapter_no_expone_update_ni_delete(
        self, repo: JsonlRepositorioEventos
    ) -> None:
        """RN-03 (inmutable) y RN-07 (append-only) cumplidos estructuralmente."""
        for metodo in ("update", "delete", "remove", "eliminar", "actualizar"):
            assert not hasattr(repo, metodo), (
                f"{metodo}() rompería RN-03/RN-07; no debe existir en el adapter."
            )

    def test_rn03_rn07_protocol_no_expone_update_ni_delete(self) -> None:
        atributos_protocol = {a for a in dir(RepositorioEventos) if not a.startswith("_")}
        prohibidos = {"update", "delete", "remove", "eliminar", "actualizar"}
        assert atributos_protocol.isdisjoint(prohibidos)

    def test_dos_appends_consecutivos_solo_crecen_el_archivo(
        self, repo: JsonlRepositorioEventos
    ) -> None:
        """Append-only: el tamaño del archivo solo aumenta tras escrituras."""
        repo.append(_evento("EVT-0001"))
        tam_1 = repo.path.stat().st_size
        repo.append(_evento("EVT-0002"))
        tam_2 = repo.path.stat().st_size
        repo.append(_evento("EVT-0003"))
        tam_3 = repo.path.stat().st_size
        assert tam_1 < tam_2 < tam_3
