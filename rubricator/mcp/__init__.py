"""The MCP connector surface.

Imported only by the connector entry point. Nothing in the core imports this
package, which is what keeps `import rubricator.tools` working in an environment
that has no MCP installed -- the environment the connector's determinism rule
exists to protect.
"""
