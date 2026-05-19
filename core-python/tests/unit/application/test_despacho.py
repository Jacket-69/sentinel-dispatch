"""Tests UT de ``despachar`` — orquestador principal de la capa application.

Cobertura:
- CP-05: flota con Avanzada y Básica para Echo → elige Avanzada (sin fallback).
- RN-02 / SUBOPTIMO_RN02: única Básica para Echo/Delta → fallback marcado.
- RN-04: unidades en TALLER excluidas del cálculo.
- RN-08 / CP-10: saturación con candidatas_redireccion.

Taxonomía Normal / Borde / Error / Regla de Negocio según pauta GCS.
"""

from __future__ import annotations

import math

import pytest

import sentinel_dispatch.application.despachar_ambulancia as _da
from sentinel_dispatch.application import (
    MotivoDespacho,
    despachar,
)
from sentinel_dispatch.domain.dispatch.tipos import (
    EstadoUnidad,
    Incidente,
    TipoUnidad,
    Unidad,
)
from sentinel_dispatch.domain.routing.tipos import Arista, NoRutaDisponibleError
from sentinel_dispatch.domain.triaje.tipos import CategoriaMPDS

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _u(
    id_: str,
    tipo: TipoUnidad = TipoUnidad.AVANZADA,
    estado: EstadoUnidad = EstadoUnidad.DISPONIBLE,
    base_lat: float = -29.9077,
    base_lon: float = -71.2535,
) -> Unidad:
    return Unidad(
        id=id_,
        patente=f"AMB-{id_[1:]}",
        tipo=tipo,
        base_nombre="H",
        base_lat=base_lat,
        base_lon=base_lon,
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
# Fake GrafoVial
# ---------------------------------------------------------------------------


class FakeGrafo:
    """Grafo trivial para tests: snap por proximidad a coordenadas pre-registradas,
    aristas mínimas para que el A* termine, y tiempos parametrizables vía
    ``tiempos_override`` para forzar t_viaje específicos sin correr A* real.
    """

    def __init__(
        self,
        nodos_por_unidad: dict[str, int],
        coords_por_nodo: dict[int, tuple[float, float]] | None = None,
        nodo_incidente: int = 99,
        tiempos_override: dict[tuple[int, int], float] | None = None,
        sin_ruta_pares: set[tuple[int, int]] | None = None,
    ) -> None:
        self._nodos = nodos_por_unidad  # unidad.id -> NodoId (snap base)
        self._nodo_inc = nodo_incidente
        self._tiempos = tiempos_override or {}
        self._sin_ruta = sin_ruta_pares or set()
        # Coords: nodo 99 = incidente; cada nodo de base puede tener coords únicas
        self._coords: dict[int, tuple[float, float]] = {99: (-29.92, -71.26)}
        if coords_por_nodo:
            self._coords.update(coords_por_nodo)
        else:
            # Default: asignar coords sintéticas únicas por nodo para
            # que nodo_mas_cercano pueda distinguirlos por lat incremental.
            for idx, nid in enumerate(dict.fromkeys(nodos_por_unidad.values())):
                if nid not in self._coords:
                    self._coords[nid] = (-29.9077, -71.2535 - idx * 0.001)

    def vecinos(self, nodo: int) -> list[Arista]:
        # Aristas mínimas para que A* encuentre ruta directa entre cualquier
        # base y el nodo incidente. NO usamos esta info para tiempos cuando
        # ``tiempos_override`` está presente — interceptamos con monkeypatch.
        if nodo != self._nodo_inc:
            return [
                Arista(
                    origen=nodo,
                    destino=self._nodo_inc,
                    longitud_m=1000.0,
                    velocidad_efectiva_kmh=50.0,
                )
            ]
        return []

    def coordenadas(self, nodo: int) -> tuple[float, float]:
        return self._coords[nodo]

    def nodo_mas_cercano(self, lat: float, lon: float) -> int:
        # Si match con coord del incidente -> nodo_incidente
        if abs(lat - (-29.92)) < 0.01 and abs(lon - (-71.26)) < 0.01:
            return self._nodo_inc
        # Buscar el nodo de menor distancia euclidiana (snap real)
        mejor_nid = 1
        mejor_dist = float("inf")
        for nid, (cy, cx) in self._coords.items():
            if nid == self._nodo_inc:
                continue
            d = (lat - cy) ** 2 + (lon - cx) ** 2
            if d < mejor_dist:
                mejor_dist = d
                mejor_nid = nid
        return mejor_nid

    def distancia_snap_m(self, lat: float, lon: float, nodo: int) -> float:
        return 0.0


# ---------------------------------------------------------------------------
# Fixture: control de t_viaje via monkeypatch sobre a_estrella
# ---------------------------------------------------------------------------


@pytest.fixture
def t_viajes_fake(monkeypatch: pytest.MonkeyPatch) -> dict[str, float]:
    """Retorna un dict mutable; el caller lo modifica para definir t_viaje
    por unidad. monkeypatch reemplaza a_estrella para usar este dict.
    """
    tiempos: dict[str, float] = {}

    def fake_a_estrella(
        grafo: FakeGrafo,
        origen: int,
        destino: int,
        factor_hora: float,
        factor_sirena: float,
    ) -> tuple[float, list[int]]:
        for uid, nid in grafo._nodos.items():
            if nid == origen:
                t = tiempos.get(uid)
                if t is None:
                    raise NoRutaDisponibleError(f"sin t para {uid}")
                if t == math.inf:
                    raise NoRutaDisponibleError(f"inf para {uid}")
                return (t, [origen, destino])
        raise NoRutaDisponibleError("origen desconocido")

    monkeypatch.setattr(_da, "a_estrella", fake_a_estrella)
    return tiempos


# ---------------------------------------------------------------------------
# Normal — camino feliz del orquestador
# ---------------------------------------------------------------------------


class TestNormal:
    def test_unica_avanzada_disponible_para_bravo_motivo_optimo(
        self, t_viajes_fake: dict[str, float]
    ) -> None:
        """Una sola Avanzada Disponible para Bravo → motivo=OPTIMO, elegida=esa unidad."""
        t_viajes_fake["U01"] = 120.0
        flota = [_u("U01")]
        incidente = _i("I-01", CategoriaMPDS.BRAVO)
        grafo = FakeGrafo(nodos_por_unidad={"U01": 1})

        resultado = despachar(incidente, flota, grafo)

        assert resultado.motivo is MotivoDespacho.OPTIMO
        assert resultado.elegida is not None
        assert resultado.elegida.id == "U01"
        assert resultado.costo_elegida is not None
        assert resultado.costo_elegida.t_viaje_s == pytest.approx(120.0)
        assert resultado.despacho_suboptimo is False

    def test_dos_avanzadas_gana_la_de_menor_t_viaje(self, t_viajes_fake: dict[str, float]) -> None:
        """Dos Avanzadas Disponibles → elegida la de menor T_viaje, motivo=OPTIMO."""
        t_viajes_fake["U01"] = 300.0
        t_viajes_fake["U02"] = 90.0
        flota = [
            _u("U01", base_lat=-29.9077, base_lon=-71.2535),
            _u("U02", base_lat=-29.9077, base_lon=-71.2545),
        ]
        incidente = _i("I-02", CategoriaMPDS.BRAVO)
        grafo = FakeGrafo(
            nodos_por_unidad={"U01": 1, "U02": 2},
            coords_por_nodo={1: (-29.9077, -71.2535), 2: (-29.9077, -71.2545)},
        )

        resultado = despachar(incidente, flota, grafo)

        assert resultado.motivo is MotivoDespacho.OPTIMO
        assert resultado.elegida is not None
        assert resultado.elegida.id == "U02"
        assert resultado.despacho_suboptimo is False


# ---------------------------------------------------------------------------
# Borde
# ---------------------------------------------------------------------------


class TestBorde:
    def test_charlie_con_unica_basica_motivo_penalizado(
        self, t_viajes_fake: dict[str, float]
    ) -> None:
        """Charlie con única Básica Disponible → motivo=PENALIZADO, penalización=1.0."""
        t_viajes_fake["U03"] = 200.0
        flota = [_u("U03", tipo=TipoUnidad.BASICA)]
        incidente = _i("I-03", CategoriaMPDS.CHARLIE)
        grafo = FakeGrafo(nodos_por_unidad={"U03": 3})

        resultado = despachar(incidente, flota, grafo)

        assert resultado.motivo is MotivoDespacho.PENALIZADO
        assert resultado.elegida is not None
        assert resultado.elegida.id == "U03"
        assert resultado.costo_elegida is not None
        assert resultado.costo_elegida.penalizacion == pytest.approx(1.0)
        assert resultado.despacho_suboptimo is False

    def test_echo_con_avanzada_y_basica_disponibles_elige_avanzada(
        self, t_viajes_fake: dict[str, float]
    ) -> None:
        """CP-05: Echo con Avanzada y Básica disponibles → motivo=OPTIMO, elegida=Avanzada."""
        t_viajes_fake["U01"] = 150.0
        t_viajes_fake["U04"] = 100.0  # Básica más cercana, pero inelegible para Echo
        flota = [
            _u("U01", tipo=TipoUnidad.AVANZADA, base_lat=-29.9077, base_lon=-71.2535),
            _u("U04", tipo=TipoUnidad.BASICA, base_lat=-29.9077, base_lon=-71.2545),
        ]
        incidente = _i("I-04", CategoriaMPDS.ECHO)
        grafo = FakeGrafo(
            nodos_por_unidad={"U01": 1, "U04": 4},
            coords_por_nodo={1: (-29.9077, -71.2535), 4: (-29.9077, -71.2545)},
        )

        resultado = despachar(incidente, flota, grafo)

        assert resultado.motivo is MotivoDespacho.OPTIMO
        assert resultado.elegida is not None
        assert resultado.elegida.id == "U01"
        assert resultado.costo_elegida is not None
        assert resultado.costo_elegida.es_infinito is False
        assert resultado.despacho_suboptimo is False

    def test_flota_completa_en_taller_retorna_saturacion(
        self, t_viajes_fake: dict[str, float]
    ) -> None:
        """Toda la flota en TALLER → motivo=SATURACION, elegida=None."""
        # Taller excluido por RN-04 en _calcular_tiempos_viaje, sin tiempos
        flota = [
            _u("U05", estado=EstadoUnidad.TALLER),
            _u("U06", estado=EstadoUnidad.TALLER),
        ]
        incidente = _i("I-05", CategoriaMPDS.BRAVO)
        grafo = FakeGrafo(nodos_por_unidad={"U05": 5, "U06": 6})

        resultado = despachar(incidente, flota, grafo)

        assert resultado.motivo is MotivoDespacho.SATURACION
        assert resultado.elegida is None
        assert resultado.costo_elegida is None


# ---------------------------------------------------------------------------
# Error — comportamiento frente a NoRutaDisponibleError
# ---------------------------------------------------------------------------


class TestError:
    def test_una_unidad_sin_ruta_otra_con_ruta_gana_la_con_ruta(
        self, t_viajes_fake: dict[str, float]
    ) -> None:
        """Dos Avanzadas; una sin ruta (inf) → la otra gana con motivo=OPTIMO."""
        t_viajes_fake["U01"] = math.inf  # fake_a_estrella lanzará NoRutaDisponibleError
        t_viajes_fake["U02"] = 180.0
        flota = [
            _u("U01", base_lat=-29.9077, base_lon=-71.2535),
            _u("U02", base_lat=-29.9077, base_lon=-71.2545),
        ]
        incidente = _i("I-06", CategoriaMPDS.BRAVO)
        grafo = FakeGrafo(
            nodos_por_unidad={"U01": 1, "U02": 2},
            coords_por_nodo={1: (-29.9077, -71.2535), 2: (-29.9077, -71.2545)},
        )

        resultado = despachar(incidente, flota, grafo)

        assert resultado.motivo is MotivoDespacho.OPTIMO
        assert resultado.elegida is not None
        assert resultado.elegida.id == "U02"


# ---------------------------------------------------------------------------
# Regla de Negocio
# ---------------------------------------------------------------------------


class TestReglaDeNegocio:
    def test_rn02_cp05_unica_basica_para_echo_es_suboptimo(
        self, t_viajes_fake: dict[str, float]
    ) -> None:
        """CP-05/RN-02: única Básica para Echo → SUBOPTIMO_RN02, despacho_suboptimo=True,
        costo_elegida.es_infinito=True (penalización ∞ por la tabla), t_viaje preservado."""
        t_viajes_fake["U07"] = 240.0
        flota = [_u("U07", tipo=TipoUnidad.BASICA)]
        incidente = _i("I-07", CategoriaMPDS.ECHO)
        grafo = FakeGrafo(nodos_por_unidad={"U07": 7})

        resultado = despachar(incidente, flota, grafo)

        assert resultado.motivo is MotivoDespacho.SUBOPTIMO_RN02
        assert resultado.elegida is not None
        assert resultado.elegida.id == "U07"
        assert resultado.despacho_suboptimo is True
        assert resultado.costo_elegida is not None
        assert resultado.costo_elegida.es_infinito is True
        assert resultado.costo_elegida.t_viaje_s == pytest.approx(240.0)

    def test_rn02_dos_basicas_para_delta_gana_menor_t_viaje(
        self, t_viajes_fake: dict[str, float]
    ) -> None:
        """RN-02 fallback con dos Básicas para Delta → elegida la de menor T_viaje."""
        t_viajes_fake["U02"] = 400.0
        t_viajes_fake["U09"] = 150.0
        flota = [
            _u("U02", tipo=TipoUnidad.BASICA, base_lat=-29.9077, base_lon=-71.2535),
            _u("U09", tipo=TipoUnidad.BASICA, base_lat=-29.9077, base_lon=-71.2545),
        ]
        incidente = _i("I-08", CategoriaMPDS.DELTA)
        grafo = FakeGrafo(
            nodos_por_unidad={"U02": 2, "U09": 9},
            coords_por_nodo={2: (-29.9077, -71.2535), 9: (-29.9077, -71.2545)},
        )

        resultado = despachar(incidente, flota, grafo)

        assert resultado.motivo is MotivoDespacho.SUBOPTIMO_RN02
        assert resultado.elegida is not None
        assert resultado.elegida.id == "U09"
        assert resultado.despacho_suboptimo is True

    def test_rn02_empate_t_viaje_desempate_lex(self, t_viajes_fake: dict[str, float]) -> None:
        """RN-02 empate: U02 y U07 Básicas para Echo con mismo T_viaje → U02 (lex)."""
        t_viajes_fake["U02"] = 300.0
        t_viajes_fake["U07"] = 300.0
        flota = [
            _u("U07", tipo=TipoUnidad.BASICA),
            _u("U02", tipo=TipoUnidad.BASICA),
        ]
        incidente = _i("I-09", CategoriaMPDS.ECHO)
        grafo = FakeGrafo(nodos_por_unidad={"U07": 7, "U02": 2})

        resultado = despachar(incidente, flota, grafo)

        assert resultado.motivo is MotivoDespacho.SUBOPTIMO_RN02
        assert resultado.elegida is not None
        assert resultado.elegida.id == "U02"
        assert resultado.despacho_suboptimo is True

    def test_cp10_saturacion_con_en_ruta_incluye_candidatas_ordenadas(
        self, t_viajes_fake: dict[str, float]
    ) -> None:
        """CP-10: flota con dos EnRuta y ninguna Disponible para Bravo → SATURACION,
        candidatas_redireccion ordenadas por progreso_pct asc."""
        # EN_RUTA no entran al argmin, y Taller excluido por _calcular_tiempos_viaje
        flota = [
            _u("U03", estado=EstadoUnidad.EN_RUTA),
            _u("U08", estado=EstadoUnidad.EN_RUTA),
        ]
        incidente = _i("I-10", CategoriaMPDS.BRAVO)
        grafo = FakeGrafo(nodos_por_unidad={"U03": 3, "U08": 8})
        progreso = {"U03": 0.6, "U08": 0.3}

        resultado = despachar(incidente, flota, grafo, progreso_por_unidad=progreso)

        assert resultado.motivo is MotivoDespacho.SATURACION
        assert resultado.elegida is None
        assert resultado.saturacion is not None
        assert resultado.saturacion.saturada is True
        candidatas = resultado.saturacion.candidatas_redireccion
        assert len(candidatas) == 2
        assert candidatas[0].unidad.id == "U08"
        assert candidatas[0].progreso_pct == pytest.approx(0.3)
        assert candidatas[1].unidad.id == "U03"
        assert candidatas[1].progreso_pct == pytest.approx(0.6)

    def test_rn04_taller_excluido_avanzada_disponible_gana(
        self, t_viajes_fake: dict[str, float]
    ) -> None:
        """RN-04: Taller no entra al cálculo; la Avanzada DISPONIBLE debe ganar
        para Charlie aunque la Taller tenga t_viaje más bajo en el monkeypatch."""
        t_viajes_fake["U01"] = 200.0
        t_viajes_fake["U10"] = 50.0  # Básica más cercana, pero Charlie+Básica penalizado
        # U05 Taller: _calcular_tiempos_viaje la saltea; no tiene t_viaje calculado
        flota = [
            _u(
                "U01",
                tipo=TipoUnidad.AVANZADA,
                estado=EstadoUnidad.DISPONIBLE,
                base_lat=-29.9077,
                base_lon=-71.2535,
            ),
            _u(
                "U05",
                tipo=TipoUnidad.AVANZADA,
                estado=EstadoUnidad.TALLER,
                base_lat=-29.9077,
                base_lon=-71.2545,
            ),
            _u(
                "U10",
                tipo=TipoUnidad.BASICA,
                estado=EstadoUnidad.DISPONIBLE,
                base_lat=-29.9077,
                base_lon=-71.2555,
            ),
        ]
        incidente = _i("I-11", CategoriaMPDS.CHARLIE)
        grafo = FakeGrafo(
            nodos_por_unidad={"U01": 1, "U05": 5, "U10": 10},
            coords_por_nodo={
                1: (-29.9077, -71.2535),
                5: (-29.9077, -71.2545),
                10: (-29.9077, -71.2555),
            },
        )

        resultado = despachar(incidente, flota, grafo)

        # Charlie+Avanzada (0 penalización) vs Charlie+Básica (pen=1.0, +600s)
        # U01: costo = 200s; U10: costo = 50 + 600 = 650s → U01 gana
        assert resultado.motivo is MotivoDespacho.OPTIMO
        assert resultado.elegida is not None
        assert resultado.elegida.id == "U01"
        candidatos_ids = [c.unidad.id for c in resultado.candidatos]
        assert "U05" not in candidatos_ids


# ---------------------------------------------------------------------------
# Ruta de nodos (H3-J-1b)
# ---------------------------------------------------------------------------


class TestRutaNodos:
    def test_normal_despacho_exitoso_ruta_nodos_poblada(
        self, t_viajes_fake: dict[str, float]
    ) -> None:
        """Normal: despacho exitoso → ruta_nodos tiene ≥2 nodos, primero=base elegida, último=incidente.

        El fake_a_estrella retorna ``[origen, destino]`` donde origen es el nodo
        snap de la base de la unidad y destino es el nodo snap del incidente (99).
        """
        t_viajes_fake["U01"] = 120.0
        nodo_base_u01 = 1
        nodo_incidente = 99
        flota = [_u("U01")]
        incidente = _i("I-rn-01", CategoriaMPDS.BRAVO)
        grafo = FakeGrafo(
            nodos_por_unidad={"U01": nodo_base_u01},
            nodo_incidente=nodo_incidente,
        )

        resultado = despachar(incidente, flota, grafo)

        assert resultado.motivo is MotivoDespacho.OPTIMO
        assert resultado.elegida is not None
        assert resultado.elegida.id == "U01"
        assert len(resultado.ruta_nodos) >= 2
        # El primer nodo debe ser el snap de la base de U01
        assert resultado.ruta_nodos[0] == nodo_base_u01
        # El último nodo debe ser el snap del incidente
        assert resultado.ruta_nodos[-1] == nodo_incidente

    def test_rn02_fallback_basica_ruta_nodos_poblada(self, t_viajes_fake: dict[str, float]) -> None:
        """RN-02: fallback con única Básica para Echo → despacho_suboptimo=True y ruta_nodos no vacía.

        La ruta de la unidad elegida (Básica) debe propagarse aunque el despacho
        sea sub-óptimo por RN-02.
        """
        t_viajes_fake["U07"] = 240.0
        nodo_base_u07 = 7
        nodo_incidente = 99
        flota = [_u("U07", tipo=TipoUnidad.BASICA)]
        incidente = _i("I-rn-02", CategoriaMPDS.ECHO)
        grafo = FakeGrafo(
            nodos_por_unidad={"U07": nodo_base_u07},
            nodo_incidente=nodo_incidente,
        )

        resultado = despachar(incidente, flota, grafo)

        assert resultado.motivo is MotivoDespacho.SUBOPTIMO_RN02
        assert resultado.despacho_suboptimo is True
        assert resultado.elegida is not None
        assert resultado.elegida.id == "U07"
        # La ruta de la Básica elegida debe estar presente (no vacía)
        assert resultado.ruta_nodos != ()
        assert len(resultado.ruta_nodos) >= 2
        assert resultado.ruta_nodos[0] == nodo_base_u07
        assert resultado.ruta_nodos[-1] == nodo_incidente
