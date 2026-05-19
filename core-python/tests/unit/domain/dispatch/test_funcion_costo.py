"""Tests unitarios de la función de costo multiobjetivo (SRS sec. 2.6-C).

Módulo bajo prueba: ``sentinel_dispatch.domain.dispatch``
Casos normativos cubiertos: CP-04, CP-05, CP-11 (setup), RN-02, RN-04.
Decisión arquitectónica de referencia: ADR-0014.

Distribución:
- :class:`TestPenalizacionIdoneidad`  — función pura sobre la tabla (Normal + Error)
- :class:`TestCostoNormal`            — combinaciones finitas y costo = T_viaje
- :class:`TestCostoBorde`             — valores límite: 0, inf, 1e6
- :class:`TestCostoError`             — excepciones por entrada inválida
- :class:`TestCostoReglaDeNegocio`    — CPs normativos + RN-02, RN-04, determinismo
"""

from __future__ import annotations

import math

import pytest

from sentinel_dispatch.domain.dispatch import (
    ALPHA,
    BETA_S,
    TABLA_PENALIZACION_IDONEIDAD,
    CostoDespacho,
    EstadoUnidad,
    Incidente,
    TipoUnidad,
    TViajeInvalidoError,
    Unidad,
    UnidadInelegibleError,
    costo,
    penalizacion_idoneidad,
)
from sentinel_dispatch.domain.triaje.tipos import CategoriaMPDS

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers de construcción
# ---------------------------------------------------------------------------


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
# TestPenalizacionIdoneidad
# ---------------------------------------------------------------------------


class TestPenalizacionIdoneidad:
    """Función pura ``penalizacion_idoneidad`` sobre las 10 entradas de la tabla."""

    @pytest.mark.parametrize(
        ("categoria", "tipo", "esperado"),
        [
            (CategoriaMPDS.ECHO, TipoUnidad.AVANZADA, 0.0),
            (CategoriaMPDS.DELTA, TipoUnidad.AVANZADA, 0.0),
            (CategoriaMPDS.CHARLIE, TipoUnidad.AVANZADA, 0.0),
            (CategoriaMPDS.BRAVO, TipoUnidad.AVANZADA, 0.0),
            (CategoriaMPDS.ALPHA, TipoUnidad.AVANZADA, 0.0),
            (CategoriaMPDS.BRAVO, TipoUnidad.BASICA, 0.0),
            (CategoriaMPDS.ALPHA, TipoUnidad.BASICA, 0.0),
            (CategoriaMPDS.CHARLIE, TipoUnidad.BASICA, 1.0),
        ],
    )
    def test_penalizacion_finita(
        self, categoria: CategoriaMPDS, tipo: TipoUnidad, esperado: float
    ) -> None:
        """Las 8 combinaciones con penalización finita devuelven el valor exacto."""
        assert penalizacion_idoneidad(categoria, tipo) == esperado

    @pytest.mark.parametrize(
        ("categoria", "tipo"),
        [
            (CategoriaMPDS.ECHO, TipoUnidad.BASICA),
            (CategoriaMPDS.DELTA, TipoUnidad.BASICA),
        ],
    )
    def test_penalizacion_infinita_en_combinaciones_prohibidas(
        self, categoria: CategoriaMPDS, tipo: TipoUnidad
    ) -> None:
        """Echo/Delta + Básica devuelven ``math.inf`` (combinación prohibida por idoneidad)."""
        resultado = penalizacion_idoneidad(categoria, tipo)
        assert math.isinf(resultado)

    def test_tabla_tiene_exactamente_10_entradas(self) -> None:
        """La tabla cubre de forma exhaustiva 5 categorias x 2 tipos = 10 entradas."""
        assert len(TABLA_PENALIZACION_IDONEIDAD) == 10

    def test_constantes_alpha_beta_con_valores_normativos(self) -> None:
        """ALPHA = 1.0 y BETA_S = 600.0 según SRS sec. 2.6-C."""
        assert ALPHA == 1.0
        assert BETA_S == 600.0


# ---------------------------------------------------------------------------
# TestCostoNormal
# ---------------------------------------------------------------------------


class TestCostoNormal:
    """Llamadas a ``costo()`` con entradas finitas y penalización cero o conocida."""

    def test_charlie_avanzada_costo_igual_a_t_viaje(self) -> None:
        """Charlie + Avanzada: penalización 0 → costo total = T_viaje."""
        u = _u("U01", TipoUnidad.AVANZADA)
        i = _i("I-01", CategoriaMPDS.CHARLIE)
        resultado = costo(u, i, 300.0)
        assert resultado.valor_total_s == 300.0
        assert resultado.penalizacion == 0.0
        assert resultado.es_infinito is False

    def test_bravo_basica_costo_igual_a_t_viaje(self) -> None:
        """Bravo + Básica: penalización 0 → costo total = T_viaje."""
        u = _u("U02", TipoUnidad.BASICA)
        i = _i("I-02", CategoriaMPDS.BRAVO)
        resultado = costo(u, i, 450.0)
        assert resultado.valor_total_s == 450.0
        assert resultado.penalizacion == 0.0
        assert resultado.es_infinito is False

    def test_alpha_basica_costo_igual_a_t_viaje(self) -> None:
        """Alpha + Básica: penalización 0 → costo total = T_viaje."""
        u = _u("U03", TipoUnidad.BASICA)
        i = _i("I-03", CategoriaMPDS.ALPHA)
        resultado = costo(u, i, 120.0)
        assert resultado.valor_total_s == 120.0
        assert resultado.penalizacion == 0.0
        assert resultado.es_infinito is False

    def test_t_viaje_cero_con_penalizacion_cero(self) -> None:
        """T_viaje = 0 (base coincide con incidente): costo = 0.0."""
        u = _u("U01", TipoUnidad.AVANZADA)
        i = _i("I-04", CategoriaMPDS.BRAVO)
        resultado = costo(u, i, 0.0)
        assert resultado.valor_total_s == 0.0
        assert resultado.t_viaje_s == 0.0
        assert resultado.es_infinito is False

    def test_charlie_basica_costo_t_viaje_mas_beta(self) -> None:
        """Charlie + Básica: penalización 1.0 → costo = T_viaje + 600."""
        u = _u("U02", TipoUnidad.BASICA)
        i = _i("I-05", CategoriaMPDS.CHARLIE)
        resultado = costo(u, i, 200.0)
        assert resultado.valor_total_s == pytest.approx(200.0 + BETA_S * 1.0)
        assert resultado.penalizacion == 1.0
        assert resultado.es_infinito is False

    def test_resultado_es_costo_despacho_inmutable(self) -> None:
        """``costo()`` devuelve un ``CostoDespacho`` congelado (frozen dataclass)."""
        u = _u("U01", TipoUnidad.AVANZADA)
        i = _i("I-06", CategoriaMPDS.ALPHA)
        resultado = costo(u, i, 60.0)
        assert isinstance(resultado, CostoDespacho)
        import dataclasses

        with pytest.raises(dataclasses.FrozenInstanceError, match="cannot assign"):
            resultado.valor_total_s = 0.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TestCostoBorde
# ---------------------------------------------------------------------------


class TestCostoBorde:
    """Valores límite y condiciones de frontera en ``costo()``."""

    def test_t_viaje_infinito_produce_es_infinito_true(self) -> None:
        """T_viaje = math.inf (sin ruta A*) → ``es_infinito=True``, total inf."""
        u = _u("U01", TipoUnidad.AVANZADA)
        i = _i("I-07", CategoriaMPDS.CHARLIE)
        resultado = costo(u, i, math.inf)
        assert resultado.es_infinito is True
        assert math.isinf(resultado.valor_total_s)

    def test_t_viaje_cero_con_penalizacion_positiva(self) -> None:
        """T_viaje = 0 con penalización > 0 → costo = β · penalización."""
        u = _u("U02", TipoUnidad.BASICA)
        i = _i("I-08", CategoriaMPDS.CHARLIE)
        resultado = costo(u, i, 0.0)
        assert resultado.valor_total_s == pytest.approx(BETA_S * 1.0)
        assert resultado.t_viaje_s == 0.0
        assert resultado.es_infinito is False

    def test_t_viaje_muy_grande_no_overflow(self) -> None:
        """T_viaje = 1e6 s (≈11.5 días): no hay overflow de float."""
        u = _u("U01", TipoUnidad.AVANZADA)
        i = _i("I-09", CategoriaMPDS.DELTA)
        resultado = costo(u, i, 1e6)
        assert resultado.valor_total_s == pytest.approx(1e6)
        assert math.isfinite(resultado.valor_total_s)

    def test_estado_en_ruta_es_elegible(self) -> None:
        """Unidad EN_RUTA (re-despacho RN-06): no lanza excepción."""
        u = _u("U01", TipoUnidad.AVANZADA, EstadoUnidad.EN_RUTA)
        i = _i("I-07", CategoriaMPDS.BRAVO)
        resultado = costo(u, i, 150.0)
        assert resultado.valor_total_s == pytest.approx(150.0)

    def test_estado_en_escena_es_elegible(self) -> None:
        """Unidad EN_ESCENA (disponible para re-despacho): no lanza excepción."""
        u = _u("U01", TipoUnidad.AVANZADA, EstadoUnidad.EN_ESCENA)
        i = _i("I-08", CategoriaMPDS.ALPHA)
        resultado = costo(u, i, 75.0)
        assert resultado.valor_total_s == pytest.approx(75.0)

    def test_t_viaje_preservado_cuando_penalizacion_infinita(self) -> None:
        """Aunque el total sea inf, ``t_viaje_s`` se preserva en el dataclass (auditoría)."""
        u = _u("U02", TipoUnidad.BASICA)
        i = _i("I-10", CategoriaMPDS.ECHO)
        resultado = costo(u, i, 60.0)
        assert resultado.t_viaje_s == 60.0
        assert resultado.es_infinito is True


# ---------------------------------------------------------------------------
# TestCostoError
# ---------------------------------------------------------------------------


class TestCostoError:
    """``costo()`` lanza excepciones ante entradas inválidas."""

    def test_t_viaje_nan_lanza_t_viaje_invalido_error(self) -> None:
        """NaN no es un tiempo de viaje físicamente válido."""
        u = _u("U01", TipoUnidad.AVANZADA)
        i = _i("I-01", CategoriaMPDS.CHARLIE)
        with pytest.raises(TViajeInvalidoError, match="inválido"):
            costo(u, i, math.nan)

    def test_t_viaje_negativo_lanza_t_viaje_invalido_error(self) -> None:
        """T_viaje < 0 es físicamente imposible."""
        u = _u("U01", TipoUnidad.AVANZADA)
        i = _i("I-01", CategoriaMPDS.BRAVO)
        with pytest.raises(TViajeInvalidoError, match="inválido"):
            costo(u, i, -1.0)

    def test_t_viaje_muy_negativo_lanza_t_viaje_invalido_error(self) -> None:
        """T_viaje = -1e9 también lanza TViajeInvalidoError."""
        u = _u("U01", TipoUnidad.AVANZADA)
        i = _i("I-01", CategoriaMPDS.ALPHA)
        with pytest.raises(TViajeInvalidoError, match="inválido"):
            costo(u, i, -1e9)

    def test_unidad_en_taller_lanza_unidad_inelegible_error(self) -> None:
        """RN-04: unidad en TALLER excluida bajo cualquier circunstancia."""
        u = _u("U05", TipoUnidad.AVANZADA, EstadoUnidad.TALLER)
        i = _i("I-02", CategoriaMPDS.BRAVO)
        with pytest.raises(UnidadInelegibleError, match="RN-04"):
            costo(u, i, 300.0)

    def test_unidad_en_taller_error_incluye_id_unidad(self) -> None:
        """El mensaje de UnidadInelegibleError menciona el ID para trazabilidad."""
        u = _u("U07", TipoUnidad.BASICA, EstadoUnidad.TALLER)
        i = _i("I-03", CategoriaMPDS.CHARLIE)
        with pytest.raises(UnidadInelegibleError, match="U07"):
            costo(u, i, 100.0)

    def test_unidad_en_taller_error_previo_a_validacion_t_viaje(self) -> None:
        """Taller lanza antes que NaN — el orden de guardas no filtra mal."""
        u = _u("U08", TipoUnidad.AVANZADA, EstadoUnidad.TALLER)
        i = _i("I-04", CategoriaMPDS.DELTA)
        with pytest.raises(UnidadInelegibleError, match="RN-04"):
            costo(u, i, math.nan)


# ---------------------------------------------------------------------------
# TestCostoReglaDeNegocio
# ---------------------------------------------------------------------------


class TestCostoReglaDeNegocio:
    """Casos de prueba normativos del SRS (CP-04, CP-05, CP-11) y RN-02/RN-04."""

    def test_cp04_avanzada_lejana_gana_a_basica_cercana_charlie(self) -> None:
        """CP-04: Avanzada a 180 s < Básica a 90 s para incidente Charlie.

        U01 (Avanzada, T=180 s) → costo = 1·180 + 600·0 = 180.0
        U02 (Básica,   T=90 s)  → costo = 1·90  + 600·1 = 690.0
        Avanzada gana aunque está más lejos. Regla normativa central del SRS.
        """
        i04 = _i("I-04", CategoriaMPDS.CHARLIE)
        u01 = _u("U01", TipoUnidad.AVANZADA)
        u02 = _u("U02", TipoUnidad.BASICA)

        costo_u01 = costo(u01, i04, 180.0)
        costo_u02 = costo(u02, i04, 90.0)

        assert costo_u01.valor_total_s == pytest.approx(180.0)
        assert costo_u02.valor_total_s == pytest.approx(690.0)
        assert costo_u01.valor_total_s < costo_u02.valor_total_s

    def test_cp05_echo_basica_produce_costo_infinito(self) -> None:
        """CP-05: Echo + Básica → ``valor_total_s = math.inf``, ``es_infinito=True``."""
        u02 = _u("U02", TipoUnidad.BASICA)
        i10 = _i("I-10", CategoriaMPDS.ECHO)

        resultado = costo(u02, i10, 60.0)

        assert resultado.es_infinito is True
        assert math.isinf(resultado.valor_total_s)
        assert math.isinf(resultado.penalizacion)

    def test_cp05_t_viaje_preservado_en_costo_infinito(self) -> None:
        """CP-05 (auditoría): ``t_viaje_s`` se preserva aunque el total sea inf."""
        u02 = _u("U02", TipoUnidad.BASICA)
        i10 = _i("I-10", CategoriaMPDS.ECHO)

        resultado = costo(u02, i10, 60.0)

        assert resultado.t_viaje_s == 60.0

    def test_rn02_delta_basica_produce_costo_infinito(self) -> None:
        """RN-02 implícita: Delta + Básica también prohibida (igual que Echo + Básica)."""
        u = _u("U02", TipoUnidad.BASICA)
        i = _i("I-11", CategoriaMPDS.DELTA)

        resultado = costo(u, i, 45.0)

        assert resultado.es_infinito is True
        assert math.isinf(resultado.valor_total_s)
        assert resultado.t_viaje_s == 45.0

    def test_cp11_setup_dos_avanzadas_mismo_t_viaje_charlie_costo_igual(self) -> None:
        """CP-11 (setup): dos Avanzadas con mismo T_viaje → ``valor_total_s`` idéntico.

        Solo se verifica igualdad de costo; el desempate lexicográfico por ID
        vive en ``seleccion.py`` (PR posterior a ADR-0015).
        """
        i = _i("I-06", CategoriaMPDS.CHARLIE)
        u_a = _u("U01", TipoUnidad.AVANZADA)
        u_b = _u("U02", TipoUnidad.AVANZADA)

        costo_a = costo(u_a, i, 200.0)
        costo_b = costo(u_b, i, 200.0)

        assert costo_a.valor_total_s == costo_b.valor_total_s

    def test_rn04_taller_lanza_unidad_inelegible_error(self) -> None:
        """RN-04: la función de costo falla ruidoso ante unidad en Taller."""
        u = _u("U09", TipoUnidad.AVANZADA, EstadoUnidad.TALLER)
        i = _i("I-07", CategoriaMPDS.BRAVO)
        with pytest.raises(UnidadInelegibleError, match="RN-04"):
            costo(u, i, 50.0)

    def test_determinismo_100_ejecuciones_mismo_input(self) -> None:
        """Función pura: 100 llamadas idénticas devuelven siempre el mismo resultado."""
        u = _u("U01", TipoUnidad.AVANZADA)
        i = _i("I-05", CategoriaMPDS.CHARLIE)
        referencia = costo(u, i, 300.0)
        for _ in range(99):
            assert costo(u, i, 300.0) == referencia

    def test_echo_avanzada_costo_finito(self) -> None:
        """Echo + Avanzada: combinación ideal → penalización 0, costo = T_viaje."""
        u = _u("U01", TipoUnidad.AVANZADA)
        i = _i("I-12", CategoriaMPDS.ECHO)
        resultado = costo(u, i, 240.0)
        assert resultado.valor_total_s == pytest.approx(240.0)
        assert resultado.es_infinito is False
        assert resultado.penalizacion == 0.0
