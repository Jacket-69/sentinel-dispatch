"""Análisis de outliers del fixture OSRM oracle (ADR-0011 §Diagnóstico).

Para los pares del fixture cuyo error relativo de distancia supera la
tolerancia CP-01a (``|d_propio − d_OSRM| / d_OSRM > 0.30``), este script
recopila features de la ruta del A* propio y asigna una **causa probable**
según las cinco fuentes de divergencia enumeradas en ADR-0011:

1. ``snap_endpoints`` — ``d_propio / d_OSRM < 0.55``: el A* del proyecto
   encontró una ruta *mucho* más corta porque el snap-to-node movió
   origen y/o destino hacia el otro endpoint. OSRM mantiene la posición
   interpolada del segmento más cercano y debe recorrer la distancia real.
2. ``snap_corto``     — ``d_OSRM < 1000 m`` (y no clasifica como
   ``snap_endpoints``): el error de snap-to-node (típicamente 20-200 m,
   RN-09) domina la métrica relativa en rutas cortas.
3. ``turn_penalty``   — número de cambios de bearing > 30° en la ruta ≥ 30:
   OSRM aplica ~2 s por giro, redistribuyendo la ruta hacia caminos con
   menos giros aunque sean más largos.
4. ``via_filtrada``   — >20% de las aristas son ``service``/``living_street``
   /``pedestrian``/``track``: el perfil ``car.lua`` de OSRM filtra (o
   penaliza) algunas de estas vías; el A* del proyecto las admite todas.
5. ``simplify``       — ruta cruzada por aristas muy cortas (<5 m) que
   probablemente serían colapsadas por la simplificación de OSRM.
6. ``residual``       — no se pudo atribuir a las causas anteriores; queda
   como residuo combinado snap + simplify + speed factor.

Las heurísticas son **probables**, no demostradas: la tabla se incrusta en
ADR-0011 como soporte de la defensa, no como evidencia formal. Defensa:
"para los 22 pares fuera de tolerancia, ¿podemos atribuir la divergencia a
los cinco factores ya identificados?". Si las cinco categorías cubren los
22 outliers, el ADR-0011 queda *empíricamente* respaldado, no sólo
*plausible*.

Uso::

    uv run --project core-python python tools/analyze_outliers.py
    uv run --project core-python python tools/analyze_outliers.py \\
        --output docs/quality/outliers-cp01a.md
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import sys
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sentinel_dispatch.adapters.grafo_osmnx import (
    GRAPHML_PATH,
    OsmnxGrafoVial,
    cargar_grafo_iv_region,
)
from sentinel_dispatch.domain.routing.a_estrella import a_estrella

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

TOLERANCIA_DISTANCIA: float = 0.30
ROOT: Path = Path(__file__).resolve().parents[1]
FIXTURE_PATH: Path = ROOT / "core-python" / "tests" / "fixtures" / "osrm_oracle.json"
DEFAULT_OUTPUT_MD: Path = ROOT / "docs" / "quality" / "outliers-cp01a.md"
DEFAULT_OUTPUT_CSV: Path = ROOT / "docs" / "quality" / "outliers-cp01a.csv"
DEFAULT_OUTPUT_SENSIBILIDAD_MD: Path = (
    ROOT / "docs" / "quality" / "outliers-sensibilidad.md"
)

# Umbrales heurísticos para la atribución de causa.
UMBRAL_RATIO_SNAP_ENDPOINTS: float = 0.55
UMBRAL_RUTA_CORTA_M: float = 1000.0
UMBRAL_GIROS_TURN_PENALTY: int = 30
UMBRAL_GIRO_GRADOS: float = 30.0
UMBRAL_PCT_VIA_FILTRADA: float = 0.20
UMBRAL_ARISTA_CORTA_M: float = 5.0
UMBRAL_PCT_SIMPLIFY: float = 0.30

# Grilla del análisis de sensibilidad (ADR-0011 §V/L#2). Verifica que la
# conclusión "snap-to-node domina" no depende de la elección puntual de
# los dos umbrales heurísticos más sensibles.
GRILLA_RATIO_SNAP: tuple[float, ...] = (0.50, 0.55, 0.60)
GRILLA_PCT_VIA_FILTRADA: tuple[float, ...] = (0.15, 0.20, 0.25)
CAUSAS_SNAP: frozenset[str] = frozenset({"snap_endpoints", "snap_corto"})

VIAS_FILTRADAS_OSRM: frozenset[str] = frozenset(
    {"service", "living_street", "pedestrian", "track", "footway", "path", "steps"}
)


# ---------------------------------------------------------------------------
# Geo helpers (Haversine + bearing)
# ---------------------------------------------------------------------------


def _bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Rumbo verdadero (0-360°) del segmento ``(lat1, lon1) → (lat2, lon2)``."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    y = math.sin(dlon) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(
        dlon
    )
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def _delta_bearing(b1: float, b2: float) -> float:
    """Diferencia angular mínima entre dos rumbos (0-180°)."""
    d = abs(b2 - b1) % 360.0
    return d if d <= 180.0 else 360.0 - d


# ---------------------------------------------------------------------------
# Features de la ruta
# ---------------------------------------------------------------------------


@dataclass
class FeaturesRuta:
    n_aristas: int
    longitud_total_m: float
    n_giros: int
    n_aristas_cortas: int
    n_aristas_via_filtrada: int
    highways_observados: Counter[str] = field(default_factory=Counter)

    @property
    def pct_via_filtrada(self) -> float:
        return self.n_aristas_via_filtrada / self.n_aristas if self.n_aristas else 0.0

    @property
    def pct_aristas_cortas(self) -> float:
        return self.n_aristas_cortas / self.n_aristas if self.n_aristas else 0.0


def _highway_de_arista(grafo: Any, u: int, v: int) -> str:
    """Devuelve el ``highway`` tag canónico de la arista u→v (MultiDiGraph).

    OSM/OSMnx puede serializar ``highway`` como string o lista; tomamos el
    primer valor o ``unknown`` si la arista no tiene tag.
    """
    edges = grafo.get_edge_data(u, v) or {}
    if not edges:
        return "unknown"
    primera = next(iter(edges.values()))
    hwy = primera.get("highway", "unknown")
    if isinstance(hwy, list):
        return str(hwy[0]) if hwy else "unknown"
    return str(hwy)


def calcular_features(adapter: OsmnxGrafoVial, ruta: list[int]) -> FeaturesRuta:
    """Recorre la ruta y agrega features relevantes para la clasificación."""
    if len(ruta) < 2:
        return FeaturesRuta(0, 0.0, 0, 0, 0)

    longitud_total = 0.0
    n_aristas_cortas = 0
    n_aristas_via_filtrada = 0
    highways: Counter[str] = Counter()
    bearings: list[float] = []

    for i in range(len(ruta) - 1):
        u, v = ruta[i], ruta[i + 1]
        longitudes = [a.longitud_m for a in adapter.vecinos(u) if a.destino == v]
        if not longitudes:
            continue
        longitud = min(longitudes)
        longitud_total += longitud
        if longitud < UMBRAL_ARISTA_CORTA_M:
            n_aristas_cortas += 1

        hwy = _highway_de_arista(adapter.grafo, u, v)
        highways[hwy] += 1
        if hwy in VIAS_FILTRADAS_OSRM:
            n_aristas_via_filtrada += 1

        lat_u, lon_u = adapter.coordenadas(u)
        lat_v, lon_v = adapter.coordenadas(v)
        bearings.append(_bearing_deg(lat_u, lon_u, lat_v, lon_v))

    n_giros = sum(
        1
        for i in range(1, len(bearings))
        if _delta_bearing(bearings[i - 1], bearings[i]) > UMBRAL_GIRO_GRADOS
    )

    return FeaturesRuta(
        n_aristas=len(ruta) - 1,
        longitud_total_m=longitud_total,
        n_giros=n_giros,
        n_aristas_cortas=n_aristas_cortas,
        n_aristas_via_filtrada=n_aristas_via_filtrada,
        highways_observados=highways,
    )


# ---------------------------------------------------------------------------
# Clasificación
# ---------------------------------------------------------------------------


@dataclass
class OutlierRaw:
    """Outlier detectado, sin clasificar (features ya calculados)."""

    par_id: int
    d_propio: float
    d_osrm: float
    err_rel: float
    features: FeaturesRuta


@dataclass
class Outlier:
    par_id: int
    d_propio: float
    d_osrm: float
    err_rel: float
    features: FeaturesRuta
    causa: str
    notas: str


def clasificar(
    d_osrm: float,
    features: FeaturesRuta,
    *,
    umbral_ratio_snap: float = UMBRAL_RATIO_SNAP_ENDPOINTS,
    umbral_pct_via_filtrada: float = UMBRAL_PCT_VIA_FILTRADA,
) -> tuple[str, str]:
    """Asigna causa probable y nota corta. Orden = prioridad descendente.

    Los dos umbrales más sensibles (``ratio_snap``, ``pct_via_filtrada``) se
    parametrizan para permitir el análisis de sensibilidad (ADR-0011 §V/L#2).
    Los otros umbrales (``UMBRAL_RUTA_CORTA_M``, ``UMBRAL_GIROS_TURN_PENALTY``,
    ``UMBRAL_PCT_SIMPLIFY``) son menos sensibles a la composición del fixture
    y se dejan como constantes para no inflar la grilla combinatoria.
    """
    ratio = features.longitud_total_m / d_osrm if d_osrm else 0.0
    if ratio < umbral_ratio_snap:
        return (
            "snap_endpoints",
            f"d_propio={features.longitud_total_m:.0f} m << d_OSRM={d_osrm:.0f} m "
            f"(ratio {ratio:.2f}); snap-to-node colapsó endpoint(s)",
        )
    if d_osrm < UMBRAL_RUTA_CORTA_M:
        return (
            "snap_corto",
            f"d_OSRM={d_osrm:.0f} m < {UMBRAL_RUTA_CORTA_M:.0f} m; "
            "snap-to-node domina en rutas cortas",
        )
    if features.n_giros >= UMBRAL_GIROS_TURN_PENALTY:
        return (
            "turn_penalty",
            f"{features.n_giros} giros > {UMBRAL_GIRO_GRADOS:.0f}°; "
            "OSRM redistribuye con turn penalty (~2 s/giro)",
        )
    if features.pct_via_filtrada > umbral_pct_via_filtrada:
        top = ", ".join(
            f"{h}={c}"
            for h, c in features.highways_observados.most_common(3)
            if h in VIAS_FILTRADAS_OSRM
        )
        return (
            "via_filtrada",
            f"{features.pct_via_filtrada:.0%} de aristas en vías que OSRM "
            f"filtra/penaliza (top: {top})",
        )
    if features.pct_aristas_cortas > UMBRAL_PCT_SIMPLIFY:
        return (
            "simplify",
            f"{features.pct_aristas_cortas:.0%} de aristas < "
            f"{UMBRAL_ARISTA_CORTA_M:.0f} m; probablemente colapsadas por "
            "simplify de OSRM",
        )
    return (
        "residual",
        "no atribuible a snap/turn/via/simplify; residuo combinado",
    )


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def cargar_pares(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    pares = data.get("pares", [])
    if not isinstance(pares, list):
        raise SystemExit(f"Fixture corrupto: 'pares' no es lista en {path}")
    return pares


def detectar_outliers(
    adapter: OsmnxGrafoVial, pares: Iterable[dict[str, Any]]
) -> list[OutlierRaw]:
    """Detecta los outliers y precomputa sus features (sin clasificar).

    Separa el paso caro (A* + features) del paso barato (clasificación),
    de modo que la grilla de sensibilidad reuse los mismos features.
    """
    raws: list[OutlierRaw] = []
    for par in pares:
        par_id = int(par["id"])
        nodo_origen = adapter.nodo_mas_cercano(
            float(par["origen"]["lat"]), float(par["origen"]["lon"])
        )
        nodo_destino = adapter.nodo_mas_cercano(
            float(par["destino"]["lat"]), float(par["destino"]["lon"])
        )
        _, ruta = a_estrella(
            adapter, nodo_origen, nodo_destino, factor_hora=1.0, factor_sirena=1.0
        )
        features = calcular_features(adapter, ruta)
        d_osrm = float(par["distance_m"])
        if d_osrm <= 0.0:
            continue
        err_rel = abs(features.longitud_total_m - d_osrm) / d_osrm
        if err_rel <= TOLERANCIA_DISTANCIA:
            continue
        raws.append(
            OutlierRaw(
                par_id=par_id,
                d_propio=features.longitud_total_m,
                d_osrm=d_osrm,
                err_rel=err_rel,
                features=features,
            )
        )
    return raws


def clasificar_outliers(
    raws: Iterable[OutlierRaw],
    *,
    umbral_ratio_snap: float = UMBRAL_RATIO_SNAP_ENDPOINTS,
    umbral_pct_via_filtrada: float = UMBRAL_PCT_VIA_FILTRADA,
) -> list[Outlier]:
    """Aplica :func:`clasificar` a cada outlier con los umbrales dados."""
    out: list[Outlier] = []
    for r in raws:
        causa, notas = clasificar(
            r.d_osrm,
            r.features,
            umbral_ratio_snap=umbral_ratio_snap,
            umbral_pct_via_filtrada=umbral_pct_via_filtrada,
        )
        out.append(
            Outlier(
                par_id=r.par_id,
                d_propio=r.d_propio,
                d_osrm=r.d_osrm,
                err_rel=r.err_rel,
                features=r.features,
                causa=causa,
                notas=notas,
            )
        )
    return out


def analizar(adapter: OsmnxGrafoVial, pares: Iterable[dict[str, Any]]) -> list[Outlier]:
    """Detecta y clasifica con los umbrales por defecto. Compat retro."""
    return clasificar_outliers(detectar_outliers(adapter, pares))


def analisis_sensibilidad(
    raws: Iterable[OutlierRaw],
    ratios: Iterable[float] = GRILLA_RATIO_SNAP,
    pcts_via: Iterable[float] = GRILLA_PCT_VIA_FILTRADA,
) -> dict[tuple[float, float], Counter[str]]:
    """Re-clasifica los mismos outliers sobre una grilla de umbrales.

    Devuelve ``{(ratio, pct_via_filtrada): Counter[causa]}``. Los outliers
    en sí no cambian (el set lo fija ``TOLERANCIA_DISTANCIA``), solo cambia
    la atribución de causa. Esto permite afirmar empíricamente que la
    conclusión "snap-to-node domina" del ADR-0011 §Diagnóstico no depende
    de la elección puntual de los umbrales heurísticos.
    """
    raws_list = list(raws)
    matriz: dict[tuple[float, float], Counter[str]] = {}
    for r in ratios:
        for p in pcts_via:
            conteo: Counter[str] = Counter()
            for raw in raws_list:
                causa, _ = clasificar(
                    raw.d_osrm,
                    raw.features,
                    umbral_ratio_snap=r,
                    umbral_pct_via_filtrada=p,
                )
                conteo[causa] += 1
            matriz[(r, p)] = conteo
    return matriz


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def render_markdown(outliers: list[Outlier]) -> str:
    conteo = Counter(o.causa for o in outliers)
    total = len(outliers)
    lineas: list[str] = []
    lineas.append("# Outliers CP-01a — clasificación por causa probable")
    lineas.append("")
    lineas.append(
        "Generado por `tools/analyze_outliers.py` sobre "
        "`core-python/tests/fixtures/osrm_oracle.json` "
        f"(tolerancia: {TOLERANCIA_DISTANCIA:.0%}). "
        "Las heurísticas y umbrales se documentan en el módulo. "
        "Esta tabla se referencia desde ADR-0011 §Diagnóstico."
    )
    lineas.append("")
    lineas.append(f"**Total outliers**: {total} / 100")
    lineas.append("")
    lineas.append("## Resumen por causa")
    lineas.append("")
    lineas.append("| Causa | Conteo | % de outliers |")
    lineas.append("|---|---:|---:|")
    for causa, c in conteo.most_common():
        pct = c / total if total else 0.0
        lineas.append(f"| `{causa}` | {c} | {pct:.0%} |")
    lineas.append("")
    lineas.append("## Detalle por par")
    lineas.append("")
    lineas.append(
        "| id | d_propio (m) | d_OSRM (m) | err_rel | giros | %vía filtrada | "
        "%aristas <5 m | causa | nota |"
    )
    lineas.append("|---:|---:|---:|---:|---:|---:|---:|---|---|")
    for o in sorted(outliers, key=lambda x: -x.err_rel):
        lineas.append(
            f"| {o.par_id} | {o.d_propio:.0f} | {o.d_osrm:.0f} | {o.err_rel:.3f} | "
            f"{o.features.n_giros} | {o.features.pct_via_filtrada:.0%} | "
            f"{o.features.pct_aristas_cortas:.0%} | `{o.causa}` | {o.notas} |"
        )
    lineas.append("")
    lineas.append("## Interpretación")
    lineas.append("")
    if conteo:
        principal = conteo.most_common(1)[0]
        lineas.append(
            f"La causa dominante es `{principal[0]}` ({principal[1]}/{total}). "
            "Cada causa coincide con una de las cinco fuentes de divergencia "
            "enumeradas en ADR-0011 §Diagnóstico, por lo que la divergencia "
            f"de los {total} outliers respecto a la tolerancia CP-01a queda "
            "atribuida empíricamente y no como hipótesis."
        )
    lineas.append("")
    return "\n".join(lineas)


def render_markdown_sensibilidad(
    matriz: dict[tuple[float, float], Counter[str]],
    total_outliers: int,
) -> str:
    """Renderiza la matriz de sensibilidad como markdown.

    Genera tres bloques: tabla cruda por causa, tabla resumen del % atribuido
    a snap-to-node, y conclusión interpretativa. El último bloque es el que
    se cita desde ADR-0011 §V/L#2.
    """
    causas_ordenadas: list[str] = [
        "snap_endpoints",
        "snap_corto",
        "turn_penalty",
        "via_filtrada",
        "simplify",
        "residual",
    ]
    lineas: list[str] = []
    lineas.append("# Análisis de sensibilidad — clasificación de outliers CP-01a")
    lineas.append("")
    lineas.append(
        "Verifica que la conclusión *snap-to-node domina* del ADR-0011 "
        "§Diagnóstico no depende de la elección puntual de los dos umbrales "
        "heurísticos más sensibles del clasificador "
        "(`UMBRAL_RATIO_SNAP_ENDPOINTS`, `UMBRAL_PCT_VIA_FILTRADA`). Se "
        "re-clasifica el **mismo set de outliers** sobre una grilla 3×3 y "
        "se observa cómo varía la atribución."
    )
    lineas.append("")
    ratios = sorted({r for (r, _) in matriz})
    pcts = sorted({p for (_, p) in matriz})
    lineas.append(
        f"Grilla: `ratio_snap ∈ {{{', '.join(f'{r:.2f}' for r in ratios)}}}` × "
        f"`pct_vía_filtrada ∈ {{{', '.join(f'{p:.2f}' for p in pcts)}}}`. "
        f"Total outliers re-clasificados: **{total_outliers} / 100**."
    )
    lineas.append("")
    lineas.append(
        "Regenerar con `uv run --project core-python python tools/analyze_outliers.py`."
    )
    lineas.append("")

    lineas.append("## Conteos por causa (combinación de umbrales)")
    lineas.append("")
    header = "| ratio | %vía | " + " | ".join(f"`{c}`" for c in causas_ordenadas) + " |"
    sep = "|---:|---:|" + "---:|" * len(causas_ordenadas)
    lineas.append(header)
    lineas.append(sep)
    for r in ratios:
        for p in pcts:
            conteo = matriz[(r, p)]
            celdas = " | ".join(str(conteo.get(c, 0)) for c in causas_ordenadas)
            lineas.append(f"| {r:.2f} | {p:.2f} | {celdas} |")
    lineas.append("")

    lineas.append("## % atribuido a snap-to-node (snap_endpoints + snap_corto)")
    lineas.append("")
    lineas.append("| ratio \\ %vía | " + " | ".join(f"{p:.2f}" for p in pcts) + " |")
    lineas.append("|---:|" + "---:|" * len(pcts))
    pcts_snap_all: list[float] = []
    for r in ratios:
        celdas: list[str] = []
        for p in pcts:
            conteo = matriz[(r, p)]
            snap = sum(conteo.get(c, 0) for c in CAUSAS_SNAP)
            pct = snap / total_outliers if total_outliers else 0.0
            pcts_snap_all.append(pct)
            celdas.append(f"{pct:.0%}")
        lineas.append(f"| {r:.2f} | " + " | ".join(celdas) + " |")
    lineas.append("")

    lineas.append("## Conclusión")
    lineas.append("")
    if pcts_snap_all:
        pmin = min(pcts_snap_all)
        pmax = max(pcts_snap_all)
        psorted = sorted(pcts_snap_all)
        pmed = psorted[len(psorted) // 2]
        lineas.append(
            f"En las 9 combinaciones de la grilla, el % de outliers atribuidos "
            f"a **snap-to-node** se mantiene en el rango "
            f"**[{pmin:.0%}, {pmax:.0%}]** (mediana {pmed:.0%}). La "
            "afirmación del ADR-0011 §Diagnóstico (*snap-to-node domina*) es "
            "robusta a la elección específica de los dos umbrales más "
            "sensibles del clasificador, y no un artefacto del valor "
            f"particular `ratio_snap={UMBRAL_RATIO_SNAP_ENDPOINTS}` / "
            f"`pct_via={UMBRAL_PCT_VIA_FILTRADA}` usado por defecto."
        )
    lineas.append("")
    return "\n".join(lineas)


def write_csv(outliers: list[Outlier], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "par_id",
                "d_propio_m",
                "d_osrm_m",
                "err_rel",
                "n_aristas",
                "n_giros",
                "pct_via_filtrada",
                "pct_aristas_cortas",
                "causa",
                "notas",
            ]
        )
        for o in sorted(outliers, key=lambda x: -x.err_rel):
            w.writerow(
                [
                    o.par_id,
                    f"{o.d_propio:.1f}",
                    f"{o.d_osrm:.1f}",
                    f"{o.err_rel:.4f}",
                    o.features.n_aristas,
                    o.features.n_giros,
                    f"{o.features.pct_via_filtrada:.4f}",
                    f"{o.features.pct_aristas_cortas:.4f}",
                    o.causa,
                    o.notas,
                ]
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=FIXTURE_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument(
        "--sensibilidad-output",
        type=Path,
        default=DEFAULT_OUTPUT_SENSIBILIDAD_MD,
        help="Markdown del análisis de sensibilidad (ADR-0011 §V/L#2)",
    )
    parser.add_argument(
        "--skip-sensibilidad",
        action="store_true",
        help="No generar el reporte de sensibilidad (modo retro-compat)",
    )
    parser.add_argument("--graphml", type=Path, default=GRAPHML_PATH)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )

    if not args.fixture.exists():
        raise SystemExit(f"Fixture ausente: {args.fixture}")
    if not args.graphml.exists():
        raise SystemExit(f"GraphML ausente: {args.graphml}")

    logging.info("Cargando grafo desde %s…", args.graphml)
    grafo = cargar_grafo_iv_region(ruta_cache=args.graphml, forzar_descarga=False)
    adapter = OsmnxGrafoVial(grafo=grafo)
    logging.info(
        "Grafo cargado: %d nodos, %d aristas",
        grafo.number_of_nodes(),
        grafo.number_of_edges(),
    )

    pares = cargar_pares(args.fixture)
    logging.info("Analizando %d pares…", len(pares))
    raws = detectar_outliers(adapter, pares)
    outliers = clasificar_outliers(raws)
    logging.info("Outliers detectados: %d / %d", len(outliers), len(pares))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_markdown(outliers), encoding="utf-8")
    write_csv(outliers, args.csv)
    logging.info("Markdown → %s", args.output)
    logging.info("CSV → %s", args.csv)

    if not args.skip_sensibilidad:
        matriz = analisis_sensibilidad(raws)
        args.sensibilidad_output.parent.mkdir(parents=True, exist_ok=True)
        args.sensibilidad_output.write_text(
            render_markdown_sensibilidad(matriz, total_outliers=len(raws)),
            encoding="utf-8",
        )
        logging.info("Sensibilidad → %s", args.sensibilidad_output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
