"""Interpreting the parts of a document whose vocabulary is open.

One module, and it is the substrate the three extensible vocabularies share:
resolution through a declared `broader` parent, and degradation that is reported
back to the caller rather than swallowed. See `resolution` for the reasoning.
"""

from rubricator.interpret.resolution import (
    Degradation,
    Resolution,
    degradation_of,
    require_known,
    resolve_declaration,
)

__all__ = [
    "Degradation",
    "Resolution",
    "degradation_of",
    "require_known",
    "resolve_declaration",
]
