"""Compatibility entry point for the historical sw-export command."""

from __future__ import annotations

import sys
from typing import Optional, Sequence

from .cli import main as swcli_main


def main(argv: Optional[Sequence[str]] = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    return swcli_main(["batch", "export", *arguments])


if __name__ == "__main__":
    raise SystemExit(main())
