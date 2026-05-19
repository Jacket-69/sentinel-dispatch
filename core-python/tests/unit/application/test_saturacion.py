"""Tests UT de ``detectar_saturacion`` (RN-08, CP-10).

Cobertura:
- RN-08: saturación de flota cuando no hay DISPONIBLES.
- CP-10: candidatas_redireccion ordenadas por progreso_pct ascendente;
  desempate lexicográfico por unidad.id.

Taxonomía Normal / Borde / Error / Regla de Negocio según pauta GCS.
"""

from __future__ import annotations

import pytest

from sentinel_dispatch.application import (
    detectar_saturacion,
)
from sentinel_dispatch.domain.dispatch.tipos import EstadoUnidad, TipoUnidad, Unidad

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _u(
    id_: str,
    tipo: TipoUnidad = TipoUnidad.AVANZADA,
    estado: EstadoUnidad = EstadoUnidad.DISPONIBLE,
) -> Unidad:
    return Unidad(
        id=id_,
        patente=f"AMB-{id_[1:]}",
        tipo=tipo,
        base_nombre="H",
        base_lat=-29.9077,
        base_lon=-71.2535,
        estado=estado,
    )


# ---------------------------------------------------------------------------
# Normal — hay al menos un DISPONIBLE
# ---------------------------------------------------------------------------


class TestNormal:
    def test_una_disponible_retorna_no_saturada_sin_candidatas(self) -> None:
        """Una DISPONIBLE basta para que saturada sea False y candidatas vacías."""
        flota = [_u("U01", estado=EstadoUnidad.DISPONIBLE)]
        resultado = detectar_saturacion(flota)
        assert resultado.saturada is False
        assert resultado.candidatas_redireccion == ()

    def test_dos_disponibles_y_una_en_ruta_no_satura(self) -> None:
        """La EN_RUTA no debe aparecer en candidatas cuando hay Disponibles."""
        flota = [
            _u("U01", estado=EstadoUnidad.DISPONIBLE),
            _u("U02", estado=EstadoUnidad.DISPONIBLE),
            _u("U03", estado=EstadoUnidad.EN_RUTA),
        ]
        resultado = detectar_saturacion(flota, progreso_por_unidad={"U03": 0.5})
        assert resultado.saturada is False
        assert resultado.candidatas_redireccion == ()


# ---------------------------------------------------------------------------
# Borde
# ---------------------------------------------------------------------------


class TestBorde:
    def test_flota_vacia_retorna_saturada_sin_candidatas(self) -> None:
        """Sin unidades no hay disponibles ni en_ruta: saturada=True, candidatas vacías."""
        resultado = detectar_saturacion([])
        assert resultado.saturada is True
        assert resultado.candidatas_redireccion == ()

    def test_una_sola_en_ruta_sin_progreso_usa_default_cero(self) -> None:
        """EN_RUTA sin entrada en progreso_por_unidad cae al default conservador 0.0."""
        flota = [_u("U04", estado=EstadoUnidad.EN_RUTA)]
        resultado = detectar_saturacion(flota)
        assert resultado.saturada is True
        assert len(resultado.candidatas_redireccion) == 1
        assert resultado.candidatas_redireccion[0].unidad.id == "U04"
        assert resultado.candidatas_redireccion[0].progreso_pct == pytest.approx(0.0)

    def test_estados_mixtos_sin_disponible_solo_en_ruta_es_candidata(self) -> None:
        """EnRuta, EnEscena y Taller: solo la EnRuta aparece en candidatas."""
        flota = [
            _u("U05", estado=EstadoUnidad.EN_RUTA),
            _u("U06", estado=EstadoUnidad.EN_ESCENA),
            _u("U07", estado=EstadoUnidad.TALLER),
        ]
        resultado = detectar_saturacion(flota, progreso_por_unidad={"U05": 0.4})
        assert resultado.saturada is True
        ids_candidatas = [c.unidad.id for c in resultado.candidatas_redireccion]
        assert "U05" in ids_candidatas
        assert "U06" not in ids_candidatas
        assert "U07" not in ids_candidatas


# ---------------------------------------------------------------------------
# Error — comportamiento defensivo (no lanza, ignora silenciosamente)
# ---------------------------------------------------------------------------


class TestError:
    def test_progreso_con_id_inexistente_se_ignora_silenciosamente(self) -> None:
        """ID desconocido en progreso_por_unidad no explota y no afecta resultados."""
        flota = [
            _u("U01", estado=EstadoUnidad.EN_RUTA),
        ]
        # "X99" no existe en la flota → debe ignorarse
        resultado = detectar_saturacion(flota, progreso_por_unidad={"X99": 0.9, "U01": 0.3})
        assert resultado.saturada is True
        assert len(resultado.candidatas_redireccion) == 1
        assert resultado.candidatas_redireccion[0].unidad.id == "U01"
        assert resultado.candidatas_redireccion[0].progreso_pct == pytest.approx(0.3)

    def test_en_ruta_sin_entrada_en_progreso_cae_a_default(self) -> None:
        """EN_RUTA cuyo id no aparece en progreso_por_unidad recibe progreso_pct=0.0."""
        flota = [
            _u("U02", estado=EstadoUnidad.EN_RUTA),
            _u("U08", estado=EstadoUnidad.EN_RUTA),
        ]
        # Solo U08 tiene entrada; U02 debe caer al default 0.0
        resultado = detectar_saturacion(flota, progreso_por_unidad={"U08": 0.5})
        assert resultado.saturada is True
        progresos = {c.unidad.id: c.progreso_pct for c in resultado.candidatas_redireccion}
        assert progresos["U02"] == pytest.approx(0.0)
        assert progresos["U08"] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Regla de Negocio CP-10 — orden de candidatas_redireccion
# ---------------------------------------------------------------------------


class TestReglaDeNegocio:
    def test_cp10_tres_en_ruta_ordenadas_por_progreso_ascendente(self) -> None:
        """CP-10: candidatas ordenadas por progreso_pct asc; ids U01/U03/U05."""
        flota = [
            _u("U03", estado=EstadoUnidad.EN_RUTA),
            _u("U05", estado=EstadoUnidad.EN_RUTA),
            _u("U01", estado=EstadoUnidad.EN_RUTA),
        ]
        progreso = {"U03": 0.2, "U05": 0.4, "U01": 0.7}
        resultado = detectar_saturacion(flota, progreso_por_unidad=progreso)

        assert resultado.saturada is True
        candidatas = resultado.candidatas_redireccion
        assert len(candidatas) == 3
        assert candidatas[0].unidad.id == "U03"
        assert candidatas[0].progreso_pct == pytest.approx(0.2)
        assert candidatas[1].unidad.id == "U05"
        assert candidatas[1].progreso_pct == pytest.approx(0.4)
        assert candidatas[2].unidad.id == "U01"
        assert candidatas[2].progreso_pct == pytest.approx(0.7)

    def test_cp10_empate_de_progreso_desempate_lexicografico(self) -> None:
        """CP-10 empate: U02 y U05 con progreso 0.3 → U02 primero por lex."""
        flota = [
            _u("U05", estado=EstadoUnidad.EN_RUTA),
            _u("U02", estado=EstadoUnidad.EN_RUTA),
        ]
        progreso = {"U05": 0.3, "U02": 0.3}
        resultado = detectar_saturacion(flota, progreso_por_unidad=progreso)

        assert resultado.saturada is True
        candidatas = resultado.candidatas_redireccion
        assert len(candidatas) == 2
        assert candidatas[0].unidad.id == "U02"
        assert candidatas[0].progreso_pct == pytest.approx(0.3)
        assert candidatas[1].unidad.id == "U05"
        assert candidatas[1].progreso_pct == pytest.approx(0.3)
