"""Validador RT-02 — compara outputs JSON de core-python vs core-java.

Lee directorios de outputs producidos por ambos cores tras ejecutar el dataset
de 12 incidentes, compara campo a campo con tolerancias configurables y
genera ``docs/quality/rt-validation-report.md`` con hallazgos clasificados.

Uso:
    python tools/compare_outputs.py \\
        --python /tmp/python-out/ \\
        --java   /tmp/java-out/ \\
        --report docs/quality/rt-validation-report.md

Tolerancias (ver ADR-0008):
    - categoria_mpds, unidad.id, despacho_suboptimo: exact match
    - eta_segundos, costo.T_viaje, costo.total:      ±5%
    - ruta (lista de nodos):                          mismo origen/destino, longitud ±10%

Estado: stub. Implementación real cuando ambos cores produzcan outputs (post-H3).
"""

from __future__ import annotations

import sys


def main() -> int:
    print(
        "tools/compare_outputs.py — stub.\n"
        "Implementar cuando core-python y core-java produzcan outputs JSON\n"
        "del dataset (post-H3 según roadmap del proyecto).",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
