# Project status (handoff file for any future session)

Last updated: 2026-11-25. Repository head: see `git log`.

## Stage
Pre-1.0 hardening. The code on `main` is `0.3.2` plus unreleased quality metrics (target `0.3.3`). **PyPI still serves 0.2.6, which crashes on a fresh install.** Publishing needs the owner (see "Outstanding").

## Implemented and tested (offline, 75 tests, Python 3.11/3.12 locally)
- Install fix: `mcp` is an optional extra; clean-venv wheel install verified.
- Piotroski F, Altman Z'', Beneish M with hand-computed tests; n/a instead of fabricated zeros.
- Quality engine: DuPont ROE, ROIC, FCF, accruals, DSO/DIO/DPO, cash conversion cycle, dilution.
- CLI errors with exit codes, retries, HTML escaping, `--no-report/--no-open`.
- CI matrix (3 OS x Py 3.10-3.13) and install smoke job; publish workflow with tag check, PyPI-conflict check, kill switch, post-release smoke test.

## Partial / not verified
- Windows and macOS CI results (cannot read Actions logs from here).
- Everything against live Yahoo data (sandbox has no access). Real-world label drift may surface more n/a values.
- Quality metrics are not yet shown in the CLI table or HTML/Excel reports (they are in `ScanResult.to_dict()["quality"]`).

## Planned (not started)
Provider abstraction (SEC EDGAR / user-supplied data), DCF with explicit assumptions, screening, portfolio analytics, rebuilt website, web app, release-please automation. See ROADMAP.md.

## Decisions
- Missing data is `None`, never 0. No assumed tax rates, no fake peer comparisons.
- Published versions are immutable; never move/delete tags; fix forward.
- Tags cannot be pushed from the Claude session (proxy 403); the owner creates releases in the GitHub UI.
- Not an investment-advice product: SEBI Research Analyst Regulations require registration for buy/sell/hold recommendations, so output is analytics plus a disclaimer.

## Outstanding (owner actions)
1. PyPI: add a Trusted Publisher (owner `shubhwade`, repo `telmus`, workflow `publish.yml`, environment `pypi`), then create GitHub release `v0.3.2` (or bump to 0.3.3 first). Alternative: local `python -m build && twine upload dist/*` with a **new project-scoped token** that never goes into chat or git.
2. Optional: GitHub environment `pypi` with required reviewers.
3. Stale tag `v0.3.0` (on old commit a166424) and unpublished `v0.3.1` remain; harmless, left untouched.

## Next actions
Surface quality metrics in CLI/reports; bump to 0.3.3; provider interface; run on real tickers once network is available and record results here.
