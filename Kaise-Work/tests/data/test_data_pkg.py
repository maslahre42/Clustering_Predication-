"""Smoke test: the src.data package skeleton is importable."""


def test_data_package_imports() -> None:
    import src.data

    assert src.data.__name__ == "src.data"
