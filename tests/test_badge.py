import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "downloads_badge", Path(__file__).parents[1] / ".github/scripts/downloads_badge.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_combines_both_packages_and_never_invents_numbers():
    b = mod.build(key="k", pepy=lambda p, k: {"isoline": 120, "telmus": 14_000}[p])
    assert b["message"] == "14.1k" and "isoline + telmus" in b["label"]


def test_keyless_mode_states_its_window():
    b = mod.build(stats=lambda p: {"isoline": 5, "telmus": 7}[p])
    assert b["message"] == "12" and "month" in b["label"]


def test_human_formatting():
    assert mod.human(999) == "999" and mod.human(1500) == "1.5k" and mod.human(2_000_000) == "2.0M"
