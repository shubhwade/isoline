from isoline import __version__
from isoline.branding import BRAND


def test_brand_matches_package_metadata():
    import pytest

    tomllib = pytest.importorskip("tomllib")
    from pathlib import Path

    meta = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())
    assert meta["project"]["name"] == BRAND.package
    assert BRAND.command in meta["project"]["scripts"]
    assert __version__


def test_report_footer_uses_brand():
    from isoline.exporters import report

    assert BRAND.command in report.__dict__["BRAND"].command


def test_website_url_is_consistent():
    """The website URL in the brand config, package metadata and docs header must agree."""
    import re
    from pathlib import Path

    import pytest

    tomllib = pytest.importorskip("tomllib")
    root = Path(__file__).parents[1]
    meta = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    assert BRAND.site_url.startswith("https://")
    assert meta["project"]["urls"]["Homepage"].rstrip("/") == BRAND.site_url.rstrip("/")
    mkdocs = (root / "mkdocs.yml").read_text(encoding="utf-8")
    homepage = re.search(r"^\s+homepage:\s*(\S+)", mkdocs, re.M)
    assert homepage and homepage.group(1).rstrip("/") == BRAND.site_url.rstrip("/")
    site = (root / "website" / "index.html").read_text(encoding="utf-8")
    assert f'<link rel="canonical" href="{BRAND.site_url.rstrip("/")}/">' in site
