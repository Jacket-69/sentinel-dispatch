"""Fixtures compartidas de los tests de integración."""

from collections.abc import Iterator

import pytest

from sentinel_dispatch.interfaces.api.main import app


@pytest.fixture(autouse=True)
def _consola_estado_limpio() -> Iterator[None]:
    """Aísla el estado en memoria de la consola entre tests.

    El overlay de estados de la flota (consola viva, ADR-0022) vive en
    ``app.state`` y persiste entre requests y entre tests, porque todos
    comparten el ``app`` módulo-global. Se resetea y se limpian los overrides
    de dependencias antes y después de cada test para evitar contaminación
    cruzada (incl. entre archivos de test).
    """
    app.state.estados_unidades = {}
    app.state.incidentes_pendientes = {}
    app.state.seq_incidentes = 0
    yield
    app.state.estados_unidades = {}
    app.state.incidentes_pendientes = {}
    app.state.seq_incidentes = 0
    app.dependency_overrides.clear()
