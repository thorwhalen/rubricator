"""User-facing disclosure text: content on disk, served like a prompt.

A disclosure is what an analysis tells its *reader* about how it was produced
-- the variance notice of ADR-0018 is the first. It is content, not code, for
the reason the prompts are (ADR-0003): a reviewer edits the wording without a
release, and both runtimes serve the same file.

**Same file contract, same loader, its own directory.** Each file carries the
prompt front matter (``id``, ``title``, ``version``, ``updated``,
``changelog``) plus ``placeholders``: the ``{name}`` fields a renderer fills
with what the analysis records -- its procedure record(s), the seeds on the
plan or on each assertion's perturbation, the independence rungs on the
assertions -- or with "not recorded". Each is a value on a ``label: value``
line rather than a word inside a sentence, because the procedures ADR-0018
prescribes vary per cell (adaptive repeats, one seed per repeat) and no single
sentence template is true of all of them. It is read through
:func:`rubricator.prompts.load_bundle`, so the dialect, the BOM handling and
the duplicate-id refusal are the prompts' own. It lives apart from them because
a prompt is handed to a model and a disclosure to a person: the prompt suite's
rules (the honesty clause, the vocabulary check) are about the first.

Rendering is ``disclose_variance``'s job (tool 17 in the frozen surface, `rubricator.tools.disclosure`),
which fills the placeholders from what was actually recorded.
This module only serves the text.

>>> d = disclosures()['variance']
>>> d.version >= 1
True
>>> sorted(d.extra['placeholders'])
['independence', 'order', 'scorings', 'traversal']
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path

from rubricator.prompts import Prompt, load_bundle

__all__ = ["DISCLOSURES_DIR", "disclosures"]

#: Where the shipped disclosures live, beside the prompts in the wheel.
DISCLOSURES_DIR = Path(__file__).parent / "data" / "disclosures"


def disclosures(root: str | Path | None = None) -> Mapping[str, Prompt]:
    """Every disclosure in ``root``, keyed by id; ``root`` is the override seam.

    Only the shipped directory is cached, as for :func:`rubricator.prompts.prompts`:
    an override is somebody iterating on wording, who must see their edit.
    """
    return _shipped() if root is None else load_bundle(Path(root))


@lru_cache(maxsize=1)
def _shipped() -> Mapping[str, Prompt]:
    return load_bundle(DISCLOSURES_DIR)
