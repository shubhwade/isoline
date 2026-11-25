# Release process

Status: **implemented** unless marked *planned*.

## How a release happens today

1. Land changes on `main` through normal commits (CI must be green: ruff, mypy, pytest on 3 OSes x Python 3.10-3.13, plus the clean-venv install smoke test).
2. Bump `__version__` in `isoline/__init__.py` (single source of truth) and add a `CHANGELOG.md` entry.
3. Create a GitHub **release/tag** `vX.Y.Z` pointing at that commit.
4. `publish.yml` runs:
   - **build** job: tag must equal the package version; the version must **not already exist on PyPI**; ruff, tests, `python -m build`, `twine check`.
   - **publish** job (environment `pypi`): uploads with Trusted Publishing (OIDC) when `PYPI_API_TOKEN` is unset, otherwise with that secret; then creates the GitHub release assets.
   - **smoke-test** job: installs `isoline==X.Y.Z` from PyPI in a clean venv and runs `isoline --version` / `--help`.

## Versioning

SemVer. Published versions are immutable: a bad release is fixed by publishing a new patch version (and optionally *yanking* the bad one on PyPI), never by overwriting or by moving/deleting tags.

| Change | Bump | Extra gate |
|---|---|---|
| Bug fix, docs | patch | none |
| New metric/feature, backwards compatible | minor | none |
| **Any change to a financial formula's output** | at least minor | must update `docs/methodology.md` and the hand-computed tests in the same PR; maintainer approval |
| Breaking CLI/API change | major | maintainer approval |

## One-time setup (needs the repository owner)

- On PyPI: *Manage project -> Publishing -> Add a trusted publisher*: owner `shubhwade`, repo `isoline`, workflow `publish.yml`, environment `pypi`.
- On GitHub: *Settings -> Environments -> pypi -> Required reviewers* = yourself. This is the approval gate: nothing reaches PyPI until you click approve.
- Never put tokens in the repo or in chat. If one is exposed, revoke it on PyPI immediately.

## Emergency release-disable switch

Set the repository **variable** `RELEASES_DISABLED` to `true` (*Settings -> Secrets and variables -> Actions -> Variables*). The build job is skipped, so nothing is published. Set it back to `false` (or delete it) to resume. To stop an in-flight run, cancel it in the Actions tab or reject the pending `pypi` environment approval.

## Rolling back

PyPI never lets a filename be re-used. Use *Yank release* on PyPI for the bad version (installs of unpinned `isoline` skip it), then ship the fixed patch release.

## Planned (not implemented)

- Automatic version bump and changelog from Conventional Commits (release-please style) with a release PR. Not enabled because it would open release PRs and tags without the owner having reviewed the policy; adopt once the commit convention is in use.
- Automated detection of "formula changed" via a golden-values test diff.
