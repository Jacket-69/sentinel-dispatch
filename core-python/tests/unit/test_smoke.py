"""Smoke test mínimo — verifica que el package importa."""

import sentinel_dispatch


def test_package_version_exists() -> None:
    assert sentinel_dispatch.__version__ == "0.1.0"
