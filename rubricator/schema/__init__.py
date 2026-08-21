"""The boundary with the companion repository's published contract.

Everything that validates goes through :class:`~rubricator.schema.source.SchemaSource`
rather than embedding a shape, so swapping the local sketch for the published
artifact is a one-line change and a test run rather than a sweep through every
tool.
"""

from rubricator.schema.source import SchemaSource, SUPPORTED_SCHEMA_VERSIONS

__all__ = ["SchemaSource", "SUPPORTED_SCHEMA_VERSIONS"]
