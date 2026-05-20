"""Validador RT-02 — compara outputs JSONL de core-python vs core-java.

Lee los directorios de outputs producidos por ambos núcleos tras ejecutar el
dataset de 12 incidentes, compara campo a campo con tolerancias configurables
(ADR-0008) y genera un reporte Markdown con los hallazgos clasificados.

Uso::

    python tools/compare_outputs.py \\
        --python /tmp/python-out/ \\
        --java   /tmp/java-out/ \\
        --report docs/quality/rt-validation-report.md

Tolerancias (ADR-0008):
    - Exact match: ``categoria_mpds``, ``unidad_seleccionada.id``,
      ``despacho_suboptimo``, ``motivo``.
    - ±5%: ``eta_segundos``, ``costo.T_viaje``, ``costo.penalizacion``,
      ``costo.total``.
    - Ruta: mismo primer nodo y mismo último nodo; longitud ±10%.

Exit codes:
    0 — todo OK o WARN (sin diferencias fuera de tolerancia).
    1 — hay al menos un FAIL (diferencia fuera de tolerancia o exact-match falla).
    2 — error de E/S (directorio no existe, archivo malformado, etc.).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constantes de tolerancia (ADR-0008)
# ---------------------------------------------------------------------------

_TOL_NUMERIC = 0.05  # ±5% para campos numéricos
_TOL_RUTA_LEN = 0.10  # ±10% para longitud de ruta

# Campos que deben hacer exact match
_EXACT_FIELDS = ("categoria_mpds", "despacho_suboptimo", "motivo")

# Campos numéricos con tolerancia ±5%
_NUMERIC_TOL_FIELDS = (
    "eta_segundos",
    "costo.T_viaje",
    "costo.penalizacion",
    "costo.total",
)

# ---------------------------------------------------------------------------
# Tipos
# ---------------------------------------------------------------------------

EstadoIncidente = str  # "OK" | "WARN" | "FAIL" | "MISSING" | "EXTRA"


def _estado_peor(a: EstadoIncidente, b: EstadoIncidente) -> EstadoIncidente:
    """Retorna el estado más grave entre dos (FAIL > WARN > OK)."""
    orden = {"OK": 0, "WARN": 1, "FAIL": 2}
    return a if orden.get(a, 0) >= orden.get(b, 0) else b


# ---------------------------------------------------------------------------
# Comparación de un par de incidentes
# ---------------------------------------------------------------------------


def _extraer_campo_anidado(doc: dict[str, Any], campo: str) -> Any:
    """Extrae un campo posiblemente anidado como 'costo.T_viaje'."""
    partes = campo.split(".", 1)
    if len(partes) == 1:
        return doc.get(campo)
    padre = doc.get(partes[0])
    if padre is None or not isinstance(padre, dict):
        return None
    return padre.get(partes[1])


def _pct_diff(a: float, b: float) -> float:
    """Diferencia porcentual relativa al valor de referencia Python."""
    if a == 0.0 and b == 0.0:
        return 0.0
    denom = max(abs(a), abs(b))
    return abs(a - b) / denom


def _comparar_par(
    id_: str, py_doc: dict[str, Any], java_doc: dict[str, Any]
) -> tuple[EstadoIncidente, list[str]]:
    """Compara dos dicts JSON (mismo incidente) y retorna (estado, notas).

    Args:
        id_: identificador del incidente (solo para mensajes de error).
        py_doc: dict Python (referencia).
        java_doc: dict Java.

    Returns:
        Tupla ``(estado, notas)`` donde ``estado`` es "OK", "WARN" o "FAIL",
        y ``notas`` es una lista de strings describiendo las diferencias.
    """
    notas: list[str] = []
    estado: EstadoIncidente = "OK"

    # Caso especial: ambos saturados
    py_sat = py_doc.get("motivo") == "saturacion"
    java_sat = java_doc.get("motivo") == "saturacion"

    # --- Exact match: motivo ---
    if py_doc.get("motivo") != java_doc.get("motivo"):
        notas.append(
            f"motivo: py={py_doc.get('motivo')!r} vs java={java_doc.get('motivo')!r}"
        )
        estado = _estado_peor(estado, "FAIL")

    # --- Exact match: categoria_mpds ---
    if py_doc.get("categoria_mpds") != java_doc.get("categoria_mpds"):
        notas.append(
            f"categoria_mpds: py={py_doc.get('categoria_mpds')!r} vs java={java_doc.get('categoria_mpds')!r}"
        )
        estado = _estado_peor(estado, "FAIL")

    # --- Exact match: despacho_suboptimo ---
    if py_doc.get("despacho_suboptimo") != java_doc.get("despacho_suboptimo"):
        notas.append(
            f"despacho_suboptimo: py={py_doc.get('despacho_suboptimo')!r} vs java={java_doc.get('despacho_suboptimo')!r}"
        )
        estado = _estado_peor(estado, "FAIL")

    # --- Exact match: unidad_seleccionada.id ---
    py_uid = (py_doc.get("unidad_seleccionada") or {}).get("id") if not py_sat else None
    java_uid = (
        (java_doc.get("unidad_seleccionada") or {}).get("id") if not java_sat else None
    )
    if py_uid != java_uid:
        notas.append(f"unidad.id: py={py_uid!r} vs java={java_uid!r}")
        estado = _estado_peor(estado, "FAIL")

    # --- Campos numéricos con ±5% ---
    for campo in _NUMERIC_TOL_FIELDS:
        py_val = _extraer_campo_anidado(py_doc, campo)
        java_val = _extraer_campo_anidado(java_doc, campo)

        # Ambos null → OK
        if py_val is None and java_val is None:
            continue
        # Uno null y el otro no → FAIL
        if (py_val is None) != (java_val is None):
            notas.append(f"{campo}: py={py_val!r} vs java={java_val!r} (uno es null)")
            estado = _estado_peor(estado, "FAIL")
            continue
        # Ambos no-null → comparar con tolerancia
        diff_pct = _pct_diff(float(py_val), float(java_val))  # type: ignore[arg-type]
        if diff_pct > _TOL_NUMERIC:
            notas.append(
                f"{campo} diff {diff_pct * 100:.1f}% (>{_TOL_NUMERIC * 100:.0f}%): py={py_val} java={java_val}"
            )
            estado = _estado_peor(estado, "FAIL")
        elif diff_pct > 0.0:
            notas.append(f"{campo} diff {diff_pct * 100:.1f}%")
            estado = _estado_peor(estado, "WARN")

    # --- Ruta: mismo primer/último nodo, longitud ±10% ---
    py_ruta: list[str] = py_doc.get("ruta") or []
    java_ruta: list[str] = java_doc.get("ruta") or []

    # Ambos vacíos (saturación) → OK
    if py_ruta or java_ruta:
        if not py_ruta and java_ruta:
            notas.append("ruta: py vacía, java no")
            estado = _estado_peor(estado, "FAIL")
        elif py_ruta and not java_ruta:
            notas.append("ruta: java vacía, py no")
            estado = _estado_peor(estado, "FAIL")
        else:
            # Comprobar primer y último nodo
            if py_ruta[0] != java_ruta[0]:
                notas.append(f"ruta.origen: py={py_ruta[0]!r} vs java={java_ruta[0]!r}")
                estado = _estado_peor(estado, "FAIL")
            if py_ruta[-1] != java_ruta[-1]:
                notas.append(
                    f"ruta.destino: py={py_ruta[-1]!r} vs java={java_ruta[-1]!r}"
                )
                estado = _estado_peor(estado, "FAIL")
            # Longitud ±10%
            len_diff = _pct_diff(float(len(py_ruta)), float(len(java_ruta)))
            if len_diff > _TOL_RUTA_LEN:
                notas.append(
                    f"ruta.len diff {len_diff * 100:.1f}%: py={len(py_ruta)} vs java={len(java_ruta)}"
                )
                estado = _estado_peor(estado, "WARN")

    return estado, notas


# ---------------------------------------------------------------------------
# Carga de archivos JSONL
# ---------------------------------------------------------------------------


def _cargar_directorio(directorio: Path) -> dict[str, dict[str, Any]]:
    """Carga todos los ``*.jsonl`` de un directorio y devuelve un dict id→doc."""
    resultado: dict[str, dict[str, Any]] = {}
    for jsonl_file in sorted(directorio.glob("*.jsonl")):
        id_ = jsonl_file.stem
        try:
            linea = jsonl_file.read_text(encoding="utf-8").strip()
            doc: dict[str, Any] = json.loads(linea)
            resultado[id_] = doc
        except (OSError, json.JSONDecodeError) as exc:
            raise OSError(f"Error leyendo {jsonl_file}: {exc}") from exc
    return resultado


# ---------------------------------------------------------------------------
# Generación del reporte Markdown
# ---------------------------------------------------------------------------


def _generar_reporte(
    python_dir: Path,
    java_dir: Path,
    resultados: dict[str, tuple[EstadoIncidente, list[str]]],
    missing: list[str],
    extra: list[str],
) -> str:
    """Genera el reporte Markdown RT-02 con tabla de resumen y detalle."""
    ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    n_comparados = len(resultados)
    n_ok = sum(1 for est, _ in resultados.values() if est == "OK")
    n_warn = sum(1 for est, _ in resultados.values() if est == "WARN")
    n_fail = sum(1 for est, _ in resultados.values() if est == "FAIL")
    n_missing = len(missing)
    n_extra = len(extra)

    lines: list[str] = []

    lines.append("# RT-02 Validation Report")
    lines.append("")
    lines.append(f"Generado: {ts}")
    lines.append(f"Python output: {python_dir}")
    lines.append(f"Java output: {java_dir}")
    lines.append("")

    lines.append("## Resumen")
    lines.append("")
    lines.append("| Métrica | Valor |")
    lines.append("|---|---|")
    lines.append(f"| Incidentes comparados | {n_comparados} |")
    lines.append(f"| OK | {n_ok} |")
    lines.append(f"| WARN | {n_warn} |")
    lines.append(f"| FAIL | {n_fail} |")
    lines.append(f"| MISSING (en Java) | {n_missing} |")
    lines.append(f"| EXTRA (en Java) | {n_extra} |")
    lines.append("")

    lines.append("## Detalle por incidente")
    lines.append("")
    lines.append("| ID | Estado | Notas |")
    lines.append("|---|---|---|")
    for id_ in sorted(resultados):
        est, notas = resultados[id_]
        nota_str = "; ".join(notas) if notas else "—"
        lines.append(f"| {id_} | {est} | {nota_str} |")
    for id_ in sorted(missing):
        lines.append(f"| {id_} | MISSING | No encontrado en directorio Java |")
    for id_ in sorted(extra):
        lines.append(f"| {id_} | EXTRA | Solo en directorio Java |")
    lines.append("")

    if n_fail > 0:
        lines.append("## Fallos")
        lines.append("")
        for id_ in sorted(resultados):
            est, notas = resultados[id_]
            if est == "FAIL":
                lines.append(f"### {id_}")
                lines.append("")
                for nota in notas:
                    lines.append(f"- {nota}")
                lines.append("")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------


def comparar(
    python_dir: Path,
    java_dir: Path,
    report_path: Path,
) -> int:
    """Compara los outputs de ambos núcleos y genera el reporte.

    Args:
        python_dir: directorio con los ``.jsonl`` de core-python.
        java_dir: directorio con los ``.jsonl`` de core-java.
        report_path: ruta del reporte Markdown a escribir.

    Returns:
        Exit code: 0=OK/WARN, 1=FAIL, 2=error E/S.
    """
    # Validar existencia de directorios
    for d, nombre in ((python_dir, "--python"), (java_dir, "--java")):
        if not d.exists():
            print(f"Error: directorio {nombre} no existe: {d}", file=sys.stderr)
            return 2
        if not d.is_dir():
            print(f"Error: {nombre} no es un directorio: {d}", file=sys.stderr)
            return 2

    # Cargar archivos
    try:
        py_docs = _cargar_directorio(python_dir)
    except OSError as exc:
        print(f"Error al leer directorio Python: {exc}", file=sys.stderr)
        return 2
    try:
        java_docs = _cargar_directorio(java_dir)
    except OSError as exc:
        print(f"Error al leer directorio Java: {exc}", file=sys.stderr)
        return 2

    py_ids = set(py_docs)
    java_ids = set(java_docs)

    missing = sorted(py_ids - java_ids)  # en Python pero no en Java
    extra = sorted(java_ids - py_ids)  # en Java pero no en Python
    comunes = sorted(py_ids & java_ids)

    # Comparar pares comunes
    resultados: dict[str, tuple[EstadoIncidente, list[str]]] = {}
    for id_ in comunes:
        est, notas = _comparar_par(id_, py_docs[id_], java_docs[id_])
        resultados[id_] = (est, notas)

    # Generar reporte
    reporte = _generar_reporte(python_dir, java_dir, resultados, missing, extra)
    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(reporte, encoding="utf-8")
    except OSError as exc:
        print(f"Error al escribir reporte: {exc}", file=sys.stderr)
        return 2

    # Resumen a stdout
    n_ok = sum(1 for est, _ in resultados.values() if est == "OK")
    n_warn = sum(1 for est, _ in resultados.values() if est == "WARN")
    n_fail = sum(1 for est, _ in resultados.values() if est == "FAIL")
    print(
        f"Comparados: {len(comunes)} | OK: {n_ok} | WARN: {n_warn} | "
        f"FAIL: {n_fail} | MISSING: {len(missing)} | EXTRA: {len(extra)}"
    )
    print(f"Reporte: {report_path}")

    if n_fail > 0 or missing:
        return 1
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parsea los argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(
        description="Validador RT-02 — compara outputs JSONL de core-python vs core-java.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--python",
        required=True,
        type=Path,
        metavar="DIR",
        help="Directorio con los .jsonl producidos por core-python.",
    )
    parser.add_argument(
        "--java",
        required=True,
        type=Path,
        metavar="DIR",
        help="Directorio con los .jsonl producidos por core-java.",
    )
    parser.add_argument(
        "--report",
        required=True,
        type=Path,
        metavar="PATH",
        help="Ruta del reporte Markdown de salida.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point del comparador."""
    args = _parse_args(argv)
    return comparar(
        python_dir=args.python,
        java_dir=args.java,
        report_path=args.report,
    )


if __name__ == "__main__":
    sys.exit(main())
