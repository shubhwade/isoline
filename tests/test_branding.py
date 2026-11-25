from telmus import __version__
from telmus.branding import BRAND


def test_brand_matches_package_metadata():
    import pytest

    tomllib = pytest.importorskip("tomllib")
    from pathlib import Path

    meta = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())
    assert meta["project"]["name"] == BRAND.package
    assert BRAND.command in meta["project"]["scripts"]
    assert __version__


def test_report_footer_uses_brand():
    from telmus.exporters import report

    assert BRAND.command in report.__dict__["BRAND"].command
