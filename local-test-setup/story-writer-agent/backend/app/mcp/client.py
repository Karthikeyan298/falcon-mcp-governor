from contextlib import asynccontextmanager
from typing import Any

from mcp import ClientSession, types
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

from app.config import settings

# Identifies this agent to any MCP gateway/server it talks to. Without this,
# the SDK falls back to a generic Implementation(name="mcp"), which makes
# every agent using the default client indistinguishable to a governance
# gateway that scopes policy by agent name.
_CLIENT_INFO = types.Implementation(name="story-creator", version="1.0")


@asynccontextmanager
async def mcp_session(server_url: str):
    """Opens a session against an HTTP-transport MCP server."""
    headers = {"X-Agent-Key": settings.mcp_agent_key} if settings.mcp_agent_key else None
    http_client = create_mcp_http_client(headers=headers)
    async with streamable_http_client(server_url, http_client=http_client) as (read, write):
        async with ClientSession(read, write, client_info=_CLIENT_INFO) as session:
            await session.initialize()
            yield session


async def list_tools(server_url: str) -> list[dict[str, Any]]:
    async with mcp_session(server_url) as session:
        result = await session.list_tools()
        return [
            {
                "name": tool.name,
                "description": tool.description or "",
                "input_schema": tool.input_schema or {},
            }
            for tool in result.tools
        ]


async def call_tool(server_url: str, tool_name: str, arguments: dict[str, Any]) -> Any:
    async with mcp_session(server_url) as session:
        result = await session.call_tool(tool_name, arguments)
        if result.is_error:
            raise RuntimeError(f"MCP tool '{tool_name}' returned an error: {result.content}")
        return result.content
