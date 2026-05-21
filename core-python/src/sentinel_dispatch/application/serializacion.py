"""Serialización canónica del :class:`ResultadoDespacho` (ADR-0017).

El schema producido aquí es el contrato bit-exacto que (a) consume
``tools/compare_outputs.py`` para la validación dual Python↔Java (RT-02),
(b) embebe el adapter :class:`JsonlRepositorioEventos` en el ``payload``
del evento ``despacho_creado`` del log JSONL (ADR-0018).

**Mantener un único punto de verdad** evita drift entre el JSONL que
emite el CLI ``run-dataset`` y el que persiste el log de eventos. Si
este schema cambia, hay que actualizar ADR-0017 y ADR-0018 en el mismo
PR (y regenerar fixtures de RT-02).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from sentinel_dispatch.application.tipos import MotivoDespacho

if TYPE_CHECKING:
    from sentinel_dispatch.application.tipos import ResultadoDespacho


def serializar_resultado_despacho(resultado: ResultadoDespacho) -> dict[str, Any]:
    """Convierte un :class:`ResultadoDespacho` al dict del schema ADR-0017.

    Schema congelado (ADR-0017):

    - ``incidente_id``: str.
    - ``categoria_mpds``: str (valor del enum, e.g. "Alpha").
    - ``unidad_seleccionada``: ``{"id": str}`` o ``null`` si saturación.
    - ``despacho_suboptimo``: bool (``true`` solo para SUBOPTIMO_RN02).
    - ``motivo``: str (valor del enum, e.g. "OPTIMO", "SATURACION").
    - ``eta_segundos``: float o ``null`` si saturación.
    - ``costo``: ``{"T_viaje": float, "penalizacion": float, "total": float}``
      o ``null`` si saturación.
    - ``ruta``: list[str] (IDs de nodo como strings; vacío en saturación).
    """
    incidente = resultado.incidente
    motivo = resultado.motivo
    es_saturacion = motivo is MotivoDespacho.SATURACION

    unidad_sel: dict[str, str] | None = None
    eta: float | None = None
    costo_dict: dict[str, float] | None = None

    if not es_saturacion and resultado.elegida is not None and resultado.costo_elegida is not None:
        unidad_sel = {"id": resultado.elegida.id}
        costo_obj = resultado.costo_elegida
        eta = costo_obj.t_viaje_s if math.isfinite(costo_obj.t_viaje_s) else None
        t_viaje = costo_obj.t_viaje_s if math.isfinite(costo_obj.t_viaje_s) else 0.0
        pen = costo_obj.penalizacion if math.isfinite(costo_obj.penalizacion) else 0.0
        total = costo_obj.valor_total_s if math.isfinite(costo_obj.valor_total_s) else 0.0
        costo_dict = {
            "T_viaje": t_viaje,
            "penalizacion": pen,
            "total": total,
        }

    # Ruta de nodos serializada como strings para evitar drift de int64 en parsers
    # JSON de otros lenguajes (Java Long, JS number). En saturación → []. (ADR-0017 §ruta)
    ruta: list[str] = [str(n) for n in resultado.ruta_nodos]

    return {
        "incidente_id": incidente.id,
        "categoria_mpds": incidente.categoria_mpds.value,
        "unidad_seleccionada": unidad_sel,
        "despacho_suboptimo": resultado.despacho_suboptimo,
        "motivo": motivo.value,
        "eta_segundos": eta,
        "costo": costo_dict,
        "ruta": ruta,
    }
