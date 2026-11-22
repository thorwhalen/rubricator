"""One loader for the ``scripts/*.py`` modules the adherence tests import (#295).

``scripts/`` is not a package, so each module is loaded from its file. ``scripts/`` is put on the path
first, so a script can import its siblings (``grading``, ``kettle_fixture``) as it does when run.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def script(name: str) -> ModuleType:
    """Load ``scripts/<name>.py`` as a module called ``name``."""
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
