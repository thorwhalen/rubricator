"""Warn when the companion repository has published schema versions this build does not vendor (#127).

Fetches each ``schema-v<N>`` tag's ``comparanda.v<N>.json`` from the companion's
public repository and compares its sha256 with the vendored pins
(:func:`rubricator.schema.drift.drift`). Prints one GitHub ``::warning::`` line
per difference and always exits 0: drift is information, not a failed build.

    python scripts/check_schema_drift.py
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import urllib.request

from rubricator.schema.drift import drift

REPO = "thorwhalen/comparanda"
API = f"https://api.github.com/repos/{REPO}/git/matching-refs/tags/schema-v"
RAW = f"https://raw.githubusercontent.com/{REPO}/schema-v{{version}}/schema/comparanda.v{{version}}.json"
TIMEOUT_SECONDS = 30


def _get(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310 - fixed https URLs
        return response.read()


def published() -> dict[int, str]:
    versions = sorted(
        int(m[1]) for ref in json.loads(_get(API)) if (m := re.fullmatch(r"refs/tags/schema-v(\d+)", ref["ref"]))
    )
    return {v: hashlib.sha256(_get(RAW.format(version=v))).hexdigest() for v in versions}


def main() -> int:
    try:
        lines = drift(published())
    except Exception as error:  # a network failure is also only a warning
        print(f"::warning::schema drift check could not run: {error}")
        return 0
    for line in lines:
        print(f"::warning::{line}")
    print("vendored schema set matches the companion's published versions." if not lines else "")
    return 0


if __name__ == "__main__":
    sys.exit(main())
