"""Exportador de logs de eventos a CSV/JSON (RF-11).

Convierte una secuencia de :class:`EventoLog` a CSV plano (apto para
LibreOffice/Excel) o JSON array indentado (apto para auditoría humana
y herramientas tabulares como ``jq``).

**Diseño**:

- El archivo fuente sigue siendo el JSONL append-only (ADR-0007); estas
  funciones producen **archivos derivados** para consumo externo. Cualquier
  edición del export NO afecta el log canónico (RN-03 preservado).
- CSV con flatten del ``payload`` anidado: ``payload.costo.total`` →
  columna ``payload_costo_total``. Listas (e.g. ``payload.ruta``) se
  serializan a JSON string en una sola celda — las herramientas
  tabulares no manejan listas como tipo nativo.
- CSV en encoding ``utf-8-sig`` (BOM) para que Excel español abra el
  archivo sin caracteres garbled. JSON sin BOM.
- Sin streaming en v1: el volumen esperado (~30-50 eventos por
  simulación, ADR-0007) cabe holgado en memoria. Si crece, refactor
  trivial a iterador-a-iterador.
"""

from __future__ import annotations

import csv
import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from pathlib import Path

    from sentinel_dispatch.ports.repositorio_eventos import EventoLog


# ---------------------------------------------------------------------------
# Aplanado de payloads anidados
# ---------------------------------------------------------------------------


def _aplanar_dict(data: dict[str, Any], prefijo: str = "") -> dict[str, Any]:
    """Aplana un dict anidado concatenando keys con ``_``.

    Listas se convierten a JSON string en una sola celda. Valores
    escalares quedan tal cual. Dicts se recursionan.

    Ejemplo:
        ``{"costo": {"T_viaje": 187.4, "total": 187.4}}`` con
        ``prefijo="payload"`` →
        ``{"payload_costo_T_viaje": 187.4, "payload_costo_total": 187.4}``.
    """
    resultado: dict[str, Any] = {}
    for key, value in data.items():
        key_compuesta = f"{prefijo}_{key}" if prefijo else key
        if isinstance(value, dict):
            resultado.update(_aplanar_dict(value, prefijo=key_compuesta))
        elif isinstance(value, list):
            resultado[key_compuesta] = json.dumps(value, ensure_ascii=False)
        else:
            resultado[key_compuesta] = value
    return resultado


def _evento_a_fila(evento: EventoLog) -> dict[str, Any]:
    """Convierte un evento a fila plana lista para ``csv.DictWriter``."""
    fila: dict[str, Any] = {
        "evento_id": evento.evento_id,
        "timestamp_iso": evento.timestamp_iso,
        "tipo": evento.tipo.value,
        "despacho_id": evento.despacho_id,
        "incidente_id": evento.incidente_id,
        "operador": evento.operador,
    }
    fila.update(_aplanar_dict(evento.payload, prefijo="payload"))
    return fila


# ---------------------------------------------------------------------------
# Exports públicos
# ---------------------------------------------------------------------------


def exportar_a_csv(eventos: Iterable[EventoLog], destino: Path) -> int:
    """Persiste los eventos como CSV plano (utf-8-sig + BOM para Excel).

    Las columnas son la **unión** de los campos planos de todos los
    eventos: si un evento no tiene una columna que sí aparece en otro,
    queda vacía en su fila. Esto soporta payloads heterogéneos sin
    truncar información.

    Args:
        eventos: iterable de :class:`EventoLog`. Se materializa una vez
            para hacer la unión de columnas (no streaming).
        destino: path absoluto al archivo CSV a crear o sobreescribir.

    Returns:
        Número de filas de datos escritas (sin contar header).
    """
    filas: Sequence[dict[str, Any]] = [_evento_a_fila(e) for e in eventos]

    columnas_raiz = [
        "evento_id",
        "timestamp_iso",
        "tipo",
        "despacho_id",
        "incidente_id",
        "operador",
    ]
    columnas_payload: list[str] = []
    seen: set[str] = set(columnas_raiz)
    for fila in filas:
        for key in fila:
            if key not in seen:
                columnas_payload.append(key)
                seen.add(key)
    columnas = columnas_raiz + columnas_payload

    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columnas, extrasaction="ignore")
        writer.writeheader()
        for fila in filas:
            writer.writerow(fila)
    return len(filas)


def exportar_a_json(eventos: Iterable[EventoLog], destino: Path) -> int:
    """Persiste los eventos como un array JSON indentado (utf-8 sin BOM).

    El formato es un array (no JSONL): un único array bien formado con N
    objetos, más usable para auditoría humana y herramientas como ``jq``.
    El log canónico fuente sigue siendo JSONL (ADR-0007); este export es
    derivado.

    Returns:
        Número de objetos escritos en el array.
    """
    objetos = [json.loads(e.model_dump_json()) for e in eventos]
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", encoding="utf-8") as f:
        json.dump(objetos, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return len(objetos)
