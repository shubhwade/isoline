"""Unit tests never touch the live internet; mark a test `network` to opt in."""

from __future__ import annotations

import pytest

from isoline.core import loaders


@pytest.fixture(autouse=True)
def _offline_by_default(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch):
    loaders.load_financials.cache_clear()
    if request.node.get_closest_marker("network"):
        yield
        return
    monkeypatch.setattr(loaders, "_sleep", lambda _s: None)

    def _blocked():
        raise OSError("live network is disabled in unit tests")

    monkeypatch.setattr(loaders, "_import_yfinance", _blocked)

    def _no_sec(*_args, **_kwargs):  # the SEC EDGAR fallback must not reach sec.gov either
        raise OSError("live network is disabled in unit tests")

    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen", _no_sec)
    yield
    loaders.load_financials.cache_clear()
