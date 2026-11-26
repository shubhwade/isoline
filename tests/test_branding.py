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


def test_website_version_label_matches_package() -> None:
    import re
    from pathlib import Path

    page = (Path(__file__).parents[1] / "website" / "index.html").read_text(encoding="utf-8")
    labels = set(re.findall(r"\bv(\d+\.\d+\.\d+)\b", page))
    assert labels == {__version__}, f"website shows {labels}, package is {__version__}"


def test_every_cli_command_is_documented() -> None:
    from pathlib import Path

    from typer.main import get_command

    from isoline.cli.app import app

    docs = (Path(__file__).parents[1] / "docs" / "cli.md").read_text(encoding="utf-8")
    commands = [name for name, cmd in get_command(app).commands.items() if not cmd.hidden]
    missing = [c for c in commands if f"## {c}" not in docs]
    assert not missing, f"undocumented commands in docs/cli.md: {missing}"
