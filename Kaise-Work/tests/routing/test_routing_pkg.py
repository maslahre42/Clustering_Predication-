"""Smoke test: the src.routing package skeleton is importable."""


def test_routing_package_imports() -> None:
    import src.routing

    assert src.routing.__name__ == "src.routing"
