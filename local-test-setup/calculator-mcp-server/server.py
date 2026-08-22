"""Simple calculator MCP server using stdio transport.

Run directly:
    python server.py

The server reads JSON-RPC from stdin and writes responses to stdout.
"""

from mcp.server.mcpserver import MCPServer

mcp = MCPServer(
    name="calculator",
    instructions="Provides basic arithmetic tools: add, subtract, multiply, divide.",
)


@mcp.tool(description="Add two numbers.")
def add(a: float, b: float) -> float:
    return a + b


@mcp.tool(description="Subtract b from a.")
def subtract(a: float, b: float) -> float:
    return a - b


@mcp.tool(description="Multiply two numbers.")
def multiply(a: float, b: float) -> float:
    return a * b


@mcp.tool(description="Divide a by b. Raises an error if b is zero.")
def divide(a: float, b: float) -> float:
    if b == 0:
        raise ValueError("Division by zero")
    return a / b


if __name__ == "__main__":
    mcp.run(transport="stdio")
