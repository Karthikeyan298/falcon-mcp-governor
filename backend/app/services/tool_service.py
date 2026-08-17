import json

from app.database import Database
from app.repositories import ToolRepository


class ToolService:
    def __init__(self, database: Database):
        self._database = database

    def list_tools(self) -> list[dict]:
        with self._database.connect() as conn:
            tools = ToolRepository(conn).list_all()
            for tool in tools:
                raw_schema = tool.pop('input_schema', None)
                tool['inputSchema'] = json.loads(raw_schema) if raw_schema else None
            return tools
