"""Tests del árbol contra el dataset de aceptación (SRS sec. 2.12).

Cada uno de los 12 incidentes del dataset se evalúa como caso independiente
mediante :func:`pytest.mark.parametrize`. La salida individual permite que
la matriz de trazabilidad (`docs/quality/trazabilidad.md`) referencie
``test_clasificacion_dataset[I-NN]`` por id.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from sentinel_dispatch.domain.triaje import (
    CategoriaMPDS,
    GrupoEtario,
    NivelDolorToracico,
    NivelSangrado,
    RespuestaTriaje,
    clasificar_mpds,
)

pytestmark = [pytest.mark.unit, pytest.mark.dataset]


# Path al dataset compartido del monorepo. Resuelto desde la ubicación del
# archivo: triaje → domain → unit → tests → core-python → monorepo.
DATASET_DIR = Path(__file__).resolve().parents[5] / "data" / "dataset"


def _cargar_incidentes() -> list[dict[str, Any]]:
    """Carga el dataset una vez al recolectar tests."""
    return json.loads((DATASET_DIR / "incidentes.json").read_text(encoding="utf-8"))


_INCIDENTES = _cargar_incidentes()


def _ids(incidente: dict[str, Any]) -> str:
    return incidente["id"]


@pytest.mark.parametrize("incidente", _INCIDENTES, ids=_ids)
def test_clasificacion_dataset(incidente: dict[str, Any]) -> None:
    r = incidente["respuestas_triaje"]
    respuesta = RespuestaTriaje(
        consciente=r["consciente"],
        respira_normal=r["respira_normal"],
        sangrado=NivelSangrado(r["sangrado"]),
        dolor_toracico=NivelDolorToracico(r["dolor_toracico"]),
        dificultad_respiratoria=r["dificultad_respiratoria"],
        grupo_etario=GrupoEtario(r["grupo_etario"]),
    )
    esperada = CategoriaMPDS(incidente["ground_truth"]["categoria_mpds"])
    obtenida = clasificar_mpds(respuesta)

    assert obtenida is esperada, (
        f"{incidente['id']}: esperada {esperada.value} (regla "
        f"{incidente['ground_truth']['regla_aplicada']}), obtenida {obtenida.value}"
    )


def test_dataset_cubre_las_cinco_categorias() -> None:
    # Garantiza que el dataset mantiene la distribución que el SRS sec. 2.12
    # promete cubrir; protege contra que alguien recorte el JSON sin querer.
    categorias = {inc["ground_truth"]["categoria_mpds"] for inc in _INCIDENTES}
    assert categorias == {"Alpha", "Bravo", "Charlie", "Delta", "Echo"}


def test_dataset_tiene_doce_incidentes() -> None:
    assert len(_INCIDENTES) == 12
