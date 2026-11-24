# Contributing

```bash
git clone https://github.com/shubhwade/telmus && cd telmus
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Before opening a pull request:

```bash
ruff check telmus tests
mypy
pytest                      # offline; add `-m network` to run live-internet tests
python -m build && twine check dist/*
```

Rules of the road
- Every bug fix gets a regression test.
- Formula changes must cite the source and include a **hand-computed** expected value (see `tests/test_scores.py`).
- Missing data is `None`, never `0`; do not invent values.
- Tests must not use the live internet unless marked `@pytest.mark.network`.
- Update `CHANGELOG.md`.

Layout: `telmus/core` (loaders, labels, engines, results), `telmus/exporters` (Excel, HTML, Power BI),
`telmus/cli` (Typer app), `telmus/mcp` (optional server).

Releasing (maintainers): bump `__version__` in `telmus/__init__.py`, update CHANGELOG, merge to
`main`, then `git tag vX.Y.Z && git push origin vX.Y.Z`. The workflow verifies tag == version, tests,
builds, runs `twine check`, waits for approval on the `pypi` environment, publishes and creates the
GitHub release. A published version can never be re-uploaded: bump instead.
