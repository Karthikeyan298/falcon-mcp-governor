import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = PROJECT_ROOT / "db_mcp_server" / "server.py"


def test_server_file_exists():
    assert SERVER_PATH.exists(), "Expected the MCP server implementation to be created"


def test_server_module_imports():
    spec = importlib.util.spec_from_file_location("db_mcp_server.server", SERVER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert module is not None
