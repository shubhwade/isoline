"""Compatibility shim: Telmus is now Isoline."""

import warnings

from isoline import *  # noqa: F401,F403
from isoline import __version__  # noqa: F401

warnings.warn(
    "telmus has been renamed isoline: use `pip install isoline` and `import isoline`.",
    DeprecationWarning,
    stacklevel=2,
)


def main() -> None:
    import sys

    print("Note: 'telmus' is now 'isoline'. Please switch to the isoline command.", file=sys.stderr)
    from isoline.cli.app import app

    app()
