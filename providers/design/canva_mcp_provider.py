"""
CanvaMcpProvider — integrates with Canva via MCP (Model Context Protocol).

v0.1: Stub. Not implemented.
v0.4+: Will use template-based filling via Canva MCP.

POLICY: Always use templates. Never freeform design.
"""

from __future__ import annotations


class CanvaMcpProvider:
    """Canva MCP integration. Not yet implemented."""

    def __init__(self, mcp_token: str = ""):
        self.token = mcp_token

    def fill_template(self, template_id: str, fields: dict, output_path: str) -> dict:
        # TODO v0.4
        raise NotImplementedError(
            "CanvaMcpProvider is not implemented in v0.1. "
            "Use MockCanvaProvider for development."
        )

    def export_design(self, design_id: str, format: str, output_path: str) -> str:
        # TODO v0.4
        raise NotImplementedError("CanvaMcpProvider not implemented in v0.1.")

    def get_capabilities(self) -> dict:
        return {
            "provider": "canva_mcp",
            "available": False,
            "version": "stub_v0.1",
            "notes": "Implement in v0.4",
        }
