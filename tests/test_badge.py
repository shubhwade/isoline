import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "downloads_badge", Path(__file__).parents[1] / ".github/scripts/downloads_badge.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# Trimmed from a real pepy.tech response (personalized-badge, period=total, units=none).
SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="114" height="20"><g fill="#fff">'
    '<text x="355" y="150" fill="#010101" fill-opacity=".3" transform="scale(.1)" textLength="590">downloads</text>'
    '<text x="355" y="140" transform="scale(.1)" textLength="590">downloads</text>'
    '<text x="905" y="150" fill="#010101" fill-opacity=".3" transform="scale(.1)" textLength="350">15533</text>'
    '<text x="905" y="140" transform="scale(.1)" textLength="350">15533</text></g></svg>'
)


def test_reads_exact_all_time_total_from_pepy_badge():
    assert mod.total_from_badge_svg(SVG) == 15533
    assert mod.total_from_badge_svg(SVG.replace("15533", "1,234,567")) == 1234567


@pytest.mark.parametrize("value", ["16k", "1.2M", "", "n/a"])
def test_refuses_rounded_or_missing_values(value):
    with pytest.raises(ValueError):
        mod.total_from_badge_svg(SVG.replace("15533", value))
    with pytest.raises(ValueError):
        mod.total_from_badge_svg("<svg></svg>")


def test_sums_isoline_and_telmus_all_time_as_one_number():
    totals = {"isoline": 1144, "telmus": 15533}
    b = mod.build(public=lambda p: totals[p])
    assert b == {"schemaVersion": 1, "label": "downloads", "message": "16.7k", "color": "B4690E"}
    assert "month" not in b["label"]
    assert mod.build(key="k", api=lambda p, k: totals[p])["message"] == "16.7k"


def test_a_failed_source_raises_instead_of_writing_a_partial_number():
    def flaky(pkg):
        if pkg == "telmus":
            raise OSError("pepy down")
        return 1144

    with pytest.raises(OSError):
        mod.build(public=flaky)


def test_human_formatting():
    assert mod.human(999) == "999" and mod.human(1500) == "1.5k" and mod.human(2_000_000) == "2.0M"
