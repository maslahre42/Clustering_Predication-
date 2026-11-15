"""Smoke test: the src.forecasting package skeleton is importable."""


def test_forecasting_package_imports() -> None:
    import src.forecasting

    assert src.forecasting.__name__ == "src.forecasting"
