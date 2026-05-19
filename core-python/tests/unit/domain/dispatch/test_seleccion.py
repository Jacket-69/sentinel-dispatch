"""Tests UT de ``seleccionar_unidad`` y ``hay_cobertura_alternativa``.

Cobertura RF-05 (selección óptima por argmin) y RN-04 (Taller excluido).
CPs cubiertos: CP-04 (Charlie + Básica vs Avanzada), CP-05 (Echo + Básica
descartada por costo ∞), CP-11 (empate de costo → desempate
lexicográfico por ``unidad.id``).

Taxonomía Normal / Borde / Error / Regla de Negocio según pauta GCS
Segunda Evaluación (``docs/quality/trazabilidad.md`` §5).
"""

from __future__ import annotations

import math

import pytest

from sentinel_dispatch.domain.dispatch import (
    EstadoUnidad,
    Incidente,
    TipoUnidad,
    Unidad,
    hay_cobertura_alternativa,
    seleccionar_unidad,
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
# Normal — camino feliz del argmin
# ---------------------------------------------------------------------------


class TestSeleccionNormal:
    def test_una_sola_unidad_disponible_es_la_elegida(self) -> None:
        u = _u("U01", TipoUnidad.AVANZADA)
        i = _i("I-01", CategoriaMPDS.BRAVO)
        r = seleccionar_unidad([u], i, {"U01": 120.0})
        assert r.elegida is not None
        assert r.elegida.id == "U01"
        assert r.costo_elegida is not None
        assert r.costo_elegida.valor_total_s == 120.0

    def test_dos_avanzadas_gana_la_mas_cercana(self) -> None:
        u1 = _u("U01", TipoUnidad.AVANZADA)
        u2 = _u("U02", TipoUnidad.AVANZADA)
        i = _i("I-04", CategoriaMPDS.CHARLIE)
        r = seleccionar_unidad([u1, u2], i, {"U01": 200.0, "U02": 90.0})
        assert r.elegida is not None
        assert r.elegida.id == "U02"

    def test_candidatos_ordenados_por_costo_ascendente(self) -> None:
        u1 = _u("U01", TipoUnidad.AVANZADA)
        u2 = _u("U02", TipoUnidad.AVANZADA)
        u3 = _u("U03", TipoUnidad.AVANZADA)
        i = _i("I-04", CategoriaMPDS.CHARLIE)
        r = seleccionar_unidad([u3, u1, u2], i, {"U01": 100.0, "U02": 200.0, "U03": 50.0})
        ids_ordenados = [c.unidad.id for c in r.candidatos]
        assert ids_ordenados == ["U03", "U01", "U02"]


# ---------------------------------------------------------------------------
# Borde — flota vacía, una sola con costo inf, todas con mismo costo
# ---------------------------------------------------------------------------


class TestSeleccionBorde:
    def test_flota_vacia_devuelve_elegida_none(self) -> None:
        i = _i("I-01", CategoriaMPDS.ALPHA)
        r = seleccionar_unidad([], i, {})
        assert r.elegida is None
        assert r.costo_elegida is None
        assert r.candidatos == ()

    def test_unica_unidad_basica_para_echo_devuelve_elegida_none(self) -> None:
        u = _u("U02", TipoUnidad.BASICA)
        i = _i("I-10", CategoriaMPDS.ECHO)
        r = seleccionar_unidad([u], i, {"U02": 60.0})
        assert r.elegida is None
        assert len(r.candidatos) == 1
        assert r.candidatos[0].costo.es_infinito is True

    def test_unidad_sin_t_viaje_provisto_se_excluye(self) -> None:
        u1 = _u("U01", TipoUnidad.AVANZADA)
        u2 = _u("U02", TipoUnidad.AVANZADA)
        i = _i("I-01", CategoriaMPDS.BRAVO)
        r = seleccionar_unidad([u1, u2], i, {"U01": 100.0})
        assert r.elegida is not None
        assert r.elegida.id == "U01"
        assert len(r.candidatos) == 1


# ---------------------------------------------------------------------------
# Error — entradas inválidas (las que se atrapan, no las que lanzan)
# ---------------------------------------------------------------------------


class TestSeleccionError:
    def test_t_viaje_negativo_propaga_t_viaje_invalido(self) -> None:
        from sentinel_dispatch.domain.dispatch import TViajeInvalidoError

        u = _u("U01", TipoUnidad.AVANZADA)
        i = _i("I-01", CategoriaMPDS.BRAVO)
        with pytest.raises(TViajeInvalidoError, match="inválido"):
            seleccionar_unidad([u], i, {"U01": -10.0})

    def test_t_viaje_nan_propaga_t_viaje_invalido(self) -> None:
        from sentinel_dispatch.domain.dispatch import TViajeInvalidoError

        u = _u("U01", TipoUnidad.AVANZADA)
        i = _i("I-01", CategoriaMPDS.BRAVO)
        with pytest.raises(TViajeInvalidoError, match="inválido"):
            seleccionar_unidad([u], i, {"U01": math.nan})

    def test_t_viaje_infinito_resulta_en_costo_infinito(self) -> None:
        u = _u("U01", TipoUnidad.AVANZADA)
        i = _i("I-01", CategoriaMPDS.BRAVO)
        r = seleccionar_unidad([u], i, {"U01": math.inf})
        assert r.elegida is None
        assert r.candidatos[0].costo.es_infinito is True


# ---------------------------------------------------------------------------
# Regla de Negocio — CP-04, CP-05, CP-11 + RN-04
# ---------------------------------------------------------------------------


class TestSeleccionReglaDeNegocio:
    def test_cp04_charlie_avanzada_lejana_gana_a_basica_cercana(self) -> None:
        """CP-04: Charlie + Avanzada lejana > Charlie + Básica cercana.

        U02 (Básica) a 90 s → costo = 90 + 600 = 690 s.
        U01 (Avanzada) a 180 s → costo = 180 + 0 = 180 s.
        Avanzada gana pese a la distancia.
        """
        u_avanzada = _u("U01", TipoUnidad.AVANZADA)
        u_basica = _u("U02", TipoUnidad.BASICA)
        i = _i("I-04", CategoriaMPDS.CHARLIE)
        r = seleccionar_unidad([u_basica, u_avanzada], i, {"U01": 180.0, "U02": 90.0})
        assert r.elegida is not None
        assert r.elegida.id == "U01"
        assert r.costo_elegida is not None
        assert r.costo_elegida.valor_total_s == 180.0

    def test_cp05_echo_basica_excluida_avanzada_lejana_gana(self) -> None:
        """CP-05: Echo + Básica (∞) excluida; Avanzada lejana sí gana."""
        u_avanzada = _u("U01", TipoUnidad.AVANZADA)
        u_basica = _u("U02", TipoUnidad.BASICA)
        i = _i("I-10", CategoriaMPDS.ECHO)
        r = seleccionar_unidad([u_basica, u_avanzada], i, {"U01": 350.0, "U02": 60.0})
        assert r.elegida is not None
        assert r.elegida.id == "U01"
        candidatos_inf = [c for c in r.candidatos if c.costo.es_infinito]
        assert len(candidatos_inf) == 1
        assert candidatos_inf[0].unidad.id == "U02"

    def test_cp11_empate_de_costo_desempate_lexicografico(self) -> None:
        """CP-11: U03 y U07 ambas Avanzada con T_viaje idéntico → U03 gana."""
        u3 = _u("U03", TipoUnidad.AVANZADA)
        u7 = _u("U07", TipoUnidad.AVANZADA)
        i = _i("I-04", CategoriaMPDS.CHARLIE)
        r = seleccionar_unidad([u7, u3], i, {"U03": 120.0, "U07": 120.0})
        assert r.elegida is not None
        assert r.elegida.id == "U03"
        assert [c.unidad.id for c in r.candidatos] == ["U03", "U07"]

    def test_rn04_unidad_taller_excluida_silenciosamente(self) -> None:
        """RN-04: una unidad en TALLER no aparece en candidatos."""
        u_taller = _u("U01", TipoUnidad.AVANZADA, EstadoUnidad.TALLER)
        u_libre = _u("U02", TipoUnidad.AVANZADA, EstadoUnidad.DISPONIBLE)
        i = _i("I-01", CategoriaMPDS.BRAVO)
        r = seleccionar_unidad([u_taller, u_libre], i, {"U01": 50.0, "U02": 200.0})
        assert r.elegida is not None
        assert r.elegida.id == "U02"
        assert all(c.unidad.id != "U01" for c in r.candidatos)


# ---------------------------------------------------------------------------
# hay_cobertura_alternativa
# ---------------------------------------------------------------------------


class TestHayCoberturaAlternativa:
    def test_otra_unidad_avanzada_cubre(self) -> None:
        u_excluida = _u("U01", TipoUnidad.AVANZADA, EstadoUnidad.EN_RUTA)
        u_alt = _u("U09", TipoUnidad.AVANZADA)
        i = _i("I-01", CategoriaMPDS.CHARLIE)
        assert hay_cobertura_alternativa(u_excluida, i, [u_alt], {"U09": 150.0}) is True

    def test_sin_alternativas_no_cubre(self) -> None:
        u_excluida = _u("U01", TipoUnidad.AVANZADA, EstadoUnidad.EN_RUTA)
        i = _i("I-01", CategoriaMPDS.CHARLIE)
        assert hay_cobertura_alternativa(u_excluida, i, [], {}) is False

    def test_alternativa_basica_para_echo_no_cubre(self) -> None:
        u_excluida = _u("U01", TipoUnidad.AVANZADA, EstadoUnidad.EN_RUTA)
        u_basica = _u("U02", TipoUnidad.BASICA)
        i = _i("I-10", CategoriaMPDS.ECHO)
        assert hay_cobertura_alternativa(u_excluida, i, [u_basica], {"U02": 60.0}) is False

    def test_la_excluida_aunque_aparezca_en_flota_no_cuenta(self) -> None:
        u_excluida = _u("U01", TipoUnidad.AVANZADA)
        i = _i("I-01", CategoriaMPDS.BRAVO)
        assert hay_cobertura_alternativa(u_excluida, i, [u_excluida], {"U01": 60.0}) is False
