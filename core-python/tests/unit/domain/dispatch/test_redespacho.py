"""Tests UT de ``evaluar_redespacho`` (RF-08 / RN-06).

Cobertura de las tres condiciones de RN-06: criticidad creciente,
progreso ≤ 50%, cobertura alternativa. CPs cubiertos: CP-06 (progreso
40% → propuesta procede), CP-07 (progreso 60% → propuesta denegada).

Taxonomía Normal / Borde / Error / Regla de Negocio según pauta GCS
Segunda Evaluación (``docs/quality/trazabilidad.md`` §5).
"""

from __future__ import annotations

import pytest

from sentinel_dispatch.domain.dispatch import (
    UMBRAL_PROGRESO_MAXIMO,
    EstadoUnidad,
    Incidente,
    TipoUnidad,
    Unidad,
    evaluar_redespacho,
)
from sentinel_dispatch.domain.triaje.tipos import CategoriaMPDS


def _u(id_: str, tipo: TipoUnidad, estado: EstadoUnidad = EstadoUnidad.DISPONIBLE) -> Unidad:
    return Unidad(
        id=id_,
        patente=f"AMB-{id_[1:]}",
        tipo=tipo,
        base_nombre="Hospital test",
        base_lat=-29.9077,
        base_lon=-71.2535,
        estado=estado,
    )


def _i(id_: str, cat: CategoriaMPDS) -> Incidente:
    return Incidente(
        id=id_,
        lat=-29.92,
        lon=-71.26,
        categoria_mpds=cat,
        timestamp_iso="2026-05-25T08:15:00-04:00",
    )


# ---------------------------------------------------------------------------
# Normal — propuestas que proceden con condiciones holgadas
# ---------------------------------------------------------------------------


class TestRedespachoNormal:
    def test_charlie_a_echo_con_progreso_30_pct_y_reemplazo_procede(self) -> None:
        u_actual = _u("U01", TipoUnidad.AVANZADA, EstadoUnidad.EN_RUTA)
        u_reempl = _u("U09", TipoUnidad.AVANZADA)
        i_actual = _i("I-01", CategoriaMPDS.CHARLIE)
        i_nuevo = _i("I-10", CategoriaMPDS.ECHO)
        prop = evaluar_redespacho(u_actual, i_actual, i_nuevo, 0.30, [u_reempl], {"U09": 150.0})
        assert prop.procede is True
        assert prop.unidad_a_redirigir.id == "U01"
        assert prop.unidad_de_reemplazo is not None
        assert prop.unidad_de_reemplazo.id == "U09"

    def test_bravo_a_delta_con_progreso_0_procede(self) -> None:
        u_actual = _u("U01", TipoUnidad.AVANZADA, EstadoUnidad.EN_RUTA)
        u_reempl = _u("U02", TipoUnidad.AVANZADA)
        i_actual = _i("I-01", CategoriaMPDS.BRAVO)
        i_nuevo = _i("I-05", CategoriaMPDS.DELTA)
        prop = evaluar_redespacho(u_actual, i_actual, i_nuevo, 0.0, [u_reempl], {"U02": 200.0})
        assert prop.procede is True


# ---------------------------------------------------------------------------
# Borde — umbrales exactos
# ---------------------------------------------------------------------------


class TestRedespachoBorde:
    def test_progreso_exactamente_50_pct_procede(self) -> None:
        u_actual = _u("U01", TipoUnidad.AVANZADA, EstadoUnidad.EN_RUTA)
        u_reempl = _u("U09", TipoUnidad.AVANZADA)
        i_actual = _i("I-01", CategoriaMPDS.CHARLIE)
        i_nuevo = _i("I-10", CategoriaMPDS.ECHO)
        prop = evaluar_redespacho(
            u_actual,
            i_actual,
            i_nuevo,
            UMBRAL_PROGRESO_MAXIMO,
            [u_reempl],
            {"U09": 150.0},
        )
        assert prop.procede is True

    def test_progreso_apenas_sobre_50_pct_denegado(self) -> None:
        u_actual = _u("U01", TipoUnidad.AVANZADA, EstadoUnidad.EN_RUTA)
        u_reempl = _u("U09", TipoUnidad.AVANZADA)
        i_actual = _i("I-01", CategoriaMPDS.CHARLIE)
        i_nuevo = _i("I-10", CategoriaMPDS.ECHO)
        prop = evaluar_redespacho(
            u_actual,
            i_actual,
            i_nuevo,
            UMBRAL_PROGRESO_MAXIMO + 0.001,
            [u_reempl],
            {"U09": 150.0},
        )
        assert prop.procede is False
        assert "Progreso" in prop.razon

    def test_alpha_a_bravo_es_criticidad_creciente(self) -> None:
        u_actual = _u("U01", TipoUnidad.AVANZADA, EstadoUnidad.EN_RUTA)
        u_reempl = _u("U09", TipoUnidad.AVANZADA)
        i_actual = _i("I-01", CategoriaMPDS.ALPHA)
        i_nuevo = _i("I-02", CategoriaMPDS.BRAVO)
        prop = evaluar_redespacho(u_actual, i_actual, i_nuevo, 0.20, [u_reempl], {"U09": 200.0})
        assert prop.procede is True


# ---------------------------------------------------------------------------
# Error — entradas que disparan los validadores subyacentes
# ---------------------------------------------------------------------------


class TestRedespachoError:
    def test_t_viaje_negativo_de_reemplazo_propaga_excepcion(self) -> None:
        from sentinel_dispatch.domain.dispatch import TViajeInvalidoError

        u_actual = _u("U01", TipoUnidad.AVANZADA, EstadoUnidad.EN_RUTA)
        u_reempl = _u("U09", TipoUnidad.AVANZADA)
        i_actual = _i("I-01", CategoriaMPDS.CHARLIE)
        i_nuevo = _i("I-10", CategoriaMPDS.ECHO)
        with pytest.raises(TViajeInvalidoError, match="inválido"):
            evaluar_redespacho(u_actual, i_actual, i_nuevo, 0.30, [u_reempl], {"U09": -1.0})


# ---------------------------------------------------------------------------
# Regla de Negocio — CP-06, CP-07 y veredictos por condición RN-06
# ---------------------------------------------------------------------------


class TestRedespachoReglaDeNegocio:
    def test_cp06_progreso_40_pct_propone_redespacho(self) -> None:
        """CP-06: U01 al 40% hacia I-01 (Charlie); llega I-10 (Echo);
        U09 disponible → propuesta procede con U09 como reemplazo.
        """
        u01 = _u("U01", TipoUnidad.AVANZADA, EstadoUnidad.EN_RUTA)
        u09 = _u("U09", TipoUnidad.AVANZADA)
        i_charlie = _i("I-01", CategoriaMPDS.CHARLIE)
        i_echo = _i("I-10", CategoriaMPDS.ECHO)
        prop = evaluar_redespacho(u01, i_charlie, i_echo, 0.40, [u09], {"U09": 150.0})
        assert prop.procede is True
        assert prop.unidad_de_reemplazo is not None
        assert prop.unidad_de_reemplazo.id == "U09"
        assert "U01" in prop.razon
        assert "I-10" in prop.razon

    def test_cp07_progreso_60_pct_deniega_redespacho(self) -> None:
        """CP-07: mismo escenario que CP-06 pero progreso=60% → no propone."""
        u01 = _u("U01", TipoUnidad.AVANZADA, EstadoUnidad.EN_RUTA)
        u09 = _u("U09", TipoUnidad.AVANZADA)
        i_charlie = _i("I-01", CategoriaMPDS.CHARLIE)
        i_echo = _i("I-10", CategoriaMPDS.ECHO)
        prop = evaluar_redespacho(u01, i_charlie, i_echo, 0.60, [u09], {"U09": 150.0})
        assert prop.procede is False
        assert prop.unidad_de_reemplazo is None
        assert "60%" in prop.razon

    def test_categoria_igual_no_es_creciente_deniega(self) -> None:
        """RN-06 cond 1: Charlie → Charlie no es criticidad creciente."""
        u01 = _u("U01", TipoUnidad.AVANZADA, EstadoUnidad.EN_RUTA)
        u09 = _u("U09", TipoUnidad.AVANZADA)
        i_a = _i("I-01", CategoriaMPDS.CHARLIE)
        i_b = _i("I-04", CategoriaMPDS.CHARLIE)
        prop = evaluar_redespacho(u01, i_a, i_b, 0.20, [u09], {"U09": 150.0})
        assert prop.procede is False
        assert "Categoría" in prop.razon

    def test_categoria_menor_deniega(self) -> None:
        """RN-06 cond 1: Echo → Charlie es decreciente."""
        u01 = _u("U01", TipoUnidad.AVANZADA, EstadoUnidad.EN_RUTA)
        u09 = _u("U09", TipoUnidad.AVANZADA)
        i_a = _i("I-10", CategoriaMPDS.ECHO)
        i_b = _i("I-01", CategoriaMPDS.CHARLIE)
        prop = evaluar_redespacho(u01, i_a, i_b, 0.10, [u09], {"U09": 150.0})
        assert prop.procede is False

    def test_sin_cobertura_alternativa_deniega(self) -> None:
        """RN-06 cond 3: si la flota disponible queda vacía o sin elegible,
        el re-despacho se deniega aunque criticidad y progreso cumplan.
        """
        u01 = _u("U01", TipoUnidad.AVANZADA, EstadoUnidad.EN_RUTA)
        i_charlie = _i("I-01", CategoriaMPDS.CHARLIE)
        i_echo = _i("I-10", CategoriaMPDS.ECHO)
        prop = evaluar_redespacho(u01, i_charlie, i_echo, 0.30, [], {})
        assert prop.procede is False
        assert "cobertura alternativa" in prop.razon

    def test_solo_basica_disponible_para_charlie_si_cubre(self) -> None:
        """Cobertura por una Básica es válida para Charlie (penalización 1.0,
        pero finita). RN-06 cond 3 se cumple.
        """
        u01 = _u("U01", TipoUnidad.AVANZADA, EstadoUnidad.EN_RUTA)
        u02 = _u("U02", TipoUnidad.BASICA)
        i_actual = _i("I-01", CategoriaMPDS.CHARLIE)
        i_nuevo = _i("I-10", CategoriaMPDS.ECHO)
        prop = evaluar_redespacho(u01, i_actual, i_nuevo, 0.20, [u02], {"U02": 200.0})
        assert prop.procede is True
        assert prop.unidad_de_reemplazo is not None
        assert prop.unidad_de_reemplazo.id == "U02"
