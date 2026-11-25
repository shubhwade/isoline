# Brand migration plan

**Status:** the owner delegated the choice and **Isoline** was selected (2026-11-25). The rename is implemented on branch `rebrand/isoline` (version 0.6.0) and is **not** merged to `main`, not published, and no domain is registered. `main` still ships as `telmus`. Domain and trademark checks remain open.

## 1. Name search

Thirty-one single words (real words and invented ones) were screened first on PyPI, where each
was looked up by exact name on 2026-11-25. Most real words are already taken (for example
`abacus`, `meridian`, `kestrel`, `vellum`, `tally`, `lemma`, `cairn`, `anvil`, `fathom`).
`cadence` and `isoline` were free. A second batch of 40 invented or rarer words was screened
the same way; 22 were free, including the finalists below.

### Shortlist (all verified absent from PyPI on 2026-11-25)

| Name | Meaning | Why it fits | Known conflicts found |
|---|---|---|---|
| **Isoline** (recommended) | A line joining points of equal value (contour, isobar). | Measurement and precision; naturally becomes a logo (parallel lines, a level line). Works as `isoline` command. | 134 GitHub repositories contain the word in their name (e.g. a graphics tool); generic technical term, so search results will be crowded and the trademark is probably weak. No financial-software company found in one web search (inconclusive). |
| Tessarin | Invented; echoes *tessera* (a tile in a mosaic). | Distinctive, easy to say, little search noise. | 34 GitHub repos with the word in the name. |
| Halden | Invented-sounding place name. | Short, serious tone. | Common surname and place name; one search for conflicts was inconclusive. |
| Altimo | Invented; echoes *altitude* and *optimum*. | Short and neutral. | 23 GitHub repos; not researched further. |
| Kelvara | Invented. | Strong phonetics, unusual. | Not researched beyond PyPI. |

**Eliminated:** `Vantor`, which was free on PyPI but is the new name of a large US
spatial-intelligence company (formerly Maxar Intelligence, rebranded Oct 2025). Other names
screened out for being taken on PyPI are listed above.

### What was NOT verified (do not assume these are clear)

- **Domains.** The sandbox cannot resolve DNS or query registries, so no domain was checked.
  Check `.com/.io/.dev` for the finalist at a registrar.
- **Trademarks.** USPTO, WIPO and the Indian registry were not searched. Run a search in
  class 9 and 42 (software) and 36 (financial services) before committing; consider a lawyer.
- **Company conflicts** were checked with a single web search per name, which is not a clearance search.

**Recommendation:** Isoline, subject to domain and trademark checks. If those fail, Tessarin.

## 2. Preserving the PyPI project and its downloads

Facts that shape the plan:

- Download counters belong to a project name. They cannot be transferred, merged or renamed,
  and a new name starts at zero. Do not claim otherwise.
- PyPI releases cannot be re-uploaded or silently replaced, and project names are not freed by
  renaming. The existing `telmus` project stays as it is, with its history.
- A Trusted Publisher is configured per PyPI project. The new project needs its own
  "pending publisher" entry before the first release workflow can create it.

Plan:

1. Keep `telmus` on PyPI. Never delete it or yank its releases.
2. After approval, publish the successor as a **new** project (new name, version `1.0.0` or
   continuing the series, owner decision) from the same repository history.
3. Release one final `telmus` version that is a thin compatibility shim: same CLI entry point,
   `Requires-Dist: <successor>`, a one-line deprecation notice on the console and in the
   description. Existing `pip install -U telmus` users then receive the successor automatically.
4. Keep the legacy README and changelog, labelled "superseded by <successor>"; the historical
   download figures stay attributed to `telmus`.
5. Keep the Python import `telmus` working for at least two minor releases through a re-export
   module that warns once.
6. Git history is preserved by renaming the package directory with `git mv` in the same
   repository (or renaming the repository; GitHub redirects the old URL).

## 3. Rename checklist (executed only after approval)

The product name lives in `telmus/branding.py` (display name, package, module, command,
tagline, URLs). A rename touches:

- [ ] `telmus/branding.py` values
- [ ] Package directory `telmus/` -> new module name (`git mv`), all `from telmus...` imports
- [ ] `pyproject.toml`: `name`, `[project.scripts]`, URLs, Trusted Publisher project name
- [ ] `.github/workflows/*`: package name in smoke tests and publish steps
- [ ] `README.md`, `docs/**`, `mkdocs.yml` (site name, repo, URLs), `website/index.html`
- [ ] MCP server name and `docs/mcp.md` config snippet
- [ ] Report footers, disclaimers, Excel/Power BI titles (read from `BRAND`)
- [ ] Environment variables (`TELMUS_CONTACT`, `TELMUS_NO_FALLBACK`): accept old and new names
- [ ] GitHub repository rename (owner action), Vercel project and domain (owner action)
- [ ] PyPI: create pending publisher, publish successor, then publish the `telmus` shim
- [ ] `CHANGELOG.md` migration entry; keep old entries unchanged

A test (`tests/test_branding.py`) already checks that `BRAND` matches `pyproject.toml`.

## 4. Approval gates

Not done without explicit approval: registering any domain, publishing any package under a new
name, renaming the GitHub repository, changing PyPI ownership, spending money.
