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


def test_website_assets_match_docs_assets() -> None:
    """The website serves its own copies; they must be the current ones, never a stale report."""
    from pathlib import Path

    root = Path(__file__).parents[1]
    for name in ("sample-report.png", "og.png"):
        assert (root / "website" / name).read_bytes() == (root / "docs" / "assets" / name).read_bytes(), name
    page = (root / "website" / "index.html").read_text(encoding="utf-8")
    assert 'src="sample-report.png"' in page and "raw.githubusercontent.com" not in page


def test_report_mark_matches_brand_files() -> None:
    from pathlib import Path

    from isoline.exporters.brand_mark import MARK_SVG

    assert MARK_SVG == (Path(__file__).parents[1] / "docs" / "assets" / "favicon.svg").read_text(encoding="utf-8").strip()


def test_website_icons_are_real_files() -> None:
    """Inline data-URI icons broke once (unescaped quotes); the site links real files instead."""
    from pathlib import Path

    root = Path(__file__).parents[1] / "website"
    page = (root / "index.html").read_text(encoding="utf-8")
    for name in ("favicon.ico", "favicon.svg", "apple-touch-icon.png", "icon-192.png"):
        assert (root / name).stat().st_size > 0 and f'href="/{name}"' in page, name
    assert "data:image/svg" not in page


def test_website_report_image_size_attributes_match_file() -> None:
    import re
    import struct
    from pathlib import Path

    root = Path(__file__).parents[1] / "website"
    page = (root / "index.html").read_text(encoding="utf-8")
    m = re.search(r'src="sample-report.png"[^>]*width="(\d+)" height="(\d+)"', page)
    header = (root / "sample-report.png").read_bytes()[:24]
    assert header[:8] == b"\x89PNG\r\n\x1a\n"
    assert m and tuple(map(int, m.groups())) == struct.unpack(">II", header[16:24])


def test_website_structured_data_and_crawl_files() -> None:
    """Search engines read these: keep the version in the JSON-LD and the crawl files in sync."""
    import json
    import re
    from pathlib import Path

    site = Path(__file__).parents[1] / "website"
    page = (site / "index.html").read_text(encoding="utf-8")
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', page, flags=re.S)
    assert len(blocks) == 1
    data = {item["@type"]: item for item in json.loads(blocks[0])}
    app = data["SoftwareApplication"]
    assert app["name"] == data["WebSite"]["name"] == "Isoline"
    assert app["softwareVersion"] == __version__
    assert app["offers"]["price"] == "0"
    assert "Isoline" in re.search(r"<title>(.*?)</title>", page).group(1)
    robots = (site / "robots.txt").read_text(encoding="utf-8")
    assert "Allow: /" in robots and "Sitemap: https://isolinee.vercel.app/sitemap.xml" in robots
    assert "<loc>https://isolinee.vercel.app/</loc>" in (site / "sitemap.xml").read_text(encoding="utf-8")
    assert f"Current version: {__version__}." in (site / "llms.txt").read_text(encoding="utf-8")
