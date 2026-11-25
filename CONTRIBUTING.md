# Contributing

```bash
git clone https://github.com/shubhwade/telmus && cd isoline
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Before opening a pull request:

```bash
ruff check isoline tests
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

Layout: `isoline/core` (loaders, labels, engines, results), `isoline/exporters` (Excel, HTML, Power BI),
`isoline/cli` (Typer app), `isoline/mcp` (optional server).

Releasing (maintainers): bump `__version__` in `isoline/__init__.py`, update CHANGELOG, merge to
`main`, then `git tag vX.Y.Z && git push origin vX.Y.Z`. The workflow verifies tag == version, tests,
builds, runs `twine check`, waits for approval on the `pypi` environment, publishes and creates the
GitHub release. A published version can never be re-uploaded: bump instead.
