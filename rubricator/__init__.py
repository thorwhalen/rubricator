"""rubricator -- turn a pile of context into a defensible comparison.

Two runtimes over one MCP tool specification (ADR-0003):

- the **connector**, an MCP server where the orchestrating Claude session
  supplies the intelligence and there is no API key at all;
- the **deployed agent**, which owns its own model access.

The rule that makes one specification serve both: **tools are deterministic,
the loop is not.** Anything reproducible -- schema validation, evidence
extraction, citation checking, completeness, agreement statistics -- is a tool.
Judgement stays in the model. A tool that embeds a model call breaks the
connector, because there is no key there.

Nothing in :mod:`rubricator.tools` may import a model client. That is enforced
by a test, not by intention.
"""

from rubricator.schema.source import SchemaSource, SUPPORTED_SCHEMA_VERSIONS

__all__ = ["SchemaSource", "SUPPORTED_SCHEMA_VERSIONS", "__version__"]

__version__ = "0.0.1"
