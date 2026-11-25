"""Central brand configuration: the one place that names the product.

A rename is implemented by changing this file plus the items in
docs/project/brand-migration.md (package directory, pyproject, workflows, URLs).
Code that prints the product name reads it from here so strings cannot drift.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Brand:
    name: str  # display name
    package: str  # PyPI distribution name
    module: str  # import name
    command: str  # console script
    tagline: str
    repo_url: str
    docs_url: str
    legacy_package: str | None = None  # kept on PyPI; points users to the successor
    successor_package: str | None = None


BRAND = Brand(
    name="Telmus",
    package="telmus",
    module="telmus",
    command="telmus",
    tagline="Financial statement analysis from the command line",
    repo_url="https://github.com/shubhwade/telmus",
    docs_url="https://shubhwade.github.io/telmus/",
)
