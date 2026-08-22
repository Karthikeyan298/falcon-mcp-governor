import hashlib
import json
import sqlite3

from app.database import Database
from app.exceptions import BadRequestError, ConflictError, NotFoundError
from app.formatting import relative_time
from app.mcp_client import McpClient
from app.policy_engine import PolicyEngine
from app.repositories import ServerRepository, SettingsRepository, ToolRepository, TrustRepository


class RiskClassifier:
    """Infers a coarse risk level for a tool from its name -- used to pick a
    conservative default policy action when a server is synced."""

    _HIGH_RISK_WORDS = ('delete', 'drop', 'remove')
    _MEDIUM_RISK_WORDS = ('create', 'update', 'insert', 'write', 'send', 'execute')

    def classify(self, tool_name: str) -> str:
        lowered = tool_name.lower()
        if any(word in lowered for word in self._HIGH_RISK_WORDS):
            return 'High'
        if any(word in lowered for word in self._MEDIUM_RISK_WORDS):
            return 'Medium'
        return 'Low'


class ServerService:
    def __init__(self, database: Database, policy_engine: PolicyEngine, risk_classifier: RiskClassifier | None = None):
        self._database = database
        self._policy_engine = policy_engine
        self._risk_classifier = risk_classifier or RiskClassifier()

    def list_servers(self) -> list[dict]:
        with self._database.connect() as conn:
            servers_repo = ServerRepository(conn)
            tools_repo = ToolRepository(conn)
            return [
                {
                    'slug': s['slug'], 'name': s['name'], 'endpoint': s['endpoint'],
                    'toolCount': tools_repo.count_for_server(s['slug']),
                    'trust': s['trust'], 'lastSynced': relative_time(s['last_synced']),
                }
                for s in servers_repo.list_all()
            ]

    @staticmethod
    def _validate_endpoint(endpoint: str) -> None:
        if not endpoint.startswith(('http://', 'https://')):
            raise BadRequestError('Endpoint must be an HTTP or HTTPS URL.')

    def create(self, *, slug: str, name: str, endpoint: str, trust: str) -> dict:
        self._validate_endpoint(endpoint)
        with self._database.connect() as conn:
            repo = ServerRepository(conn)
            if repo.exists(slug):
                raise ConflictError('A server with this slug already exists')
            repo.create(slug=slug, name=name, endpoint=endpoint, trust=trust, last_synced=self._database.now_iso())
            return {'slug': slug, 'name': name, 'endpoint': endpoint, 'toolCount': 0, 'trust': trust, 'lastSynced': 'just now'}

    def update(self, slug: str, *, name: str, endpoint: str, trust: str) -> dict:
        self._validate_endpoint(endpoint)
        with self._database.connect() as conn:
            repo = ServerRepository(conn)
            server = repo.get(slug)
            if server is None:
                raise NotFoundError('Server not found')
            repo.update(slug, name=name, endpoint=endpoint, trust=trust)
            tool_count = ToolRepository(conn).count_for_server(slug)
            return {
                'slug': slug, 'name': name, 'endpoint': endpoint, 'toolCount': tool_count,
                'trust': trust, 'lastSynced': relative_time(server['last_synced']),
            }

    def delete(self, slug: str) -> None:
        with self._database.connect() as conn:
            servers_repo = ServerRepository(conn)
            if not servers_repo.exists(slug):
                raise NotFoundError('Server not found')
            tools_repo = ToolRepository(conn)
            tool_keys = [f"{slug}.{t['name']}" for t in tools_repo.list_for_server(slug)]
            tools_repo.delete_for_server(slug)
            TrustRepository(conn).delete_many(tool_keys)
            servers_repo.delete(slug)

    def sync(self, slug: str) -> dict:
        with self._database.connect() as conn:
            servers_repo = ServerRepository(conn)
            server = servers_repo.get(slug)
            if server is None:
                raise NotFoundError('Server not found')

            if server['endpoint'].startswith(('http://', 'https://')):
                self._sync_real_tools(conn, slug=slug, server=server)

            now = self._database.now_iso()
            servers_repo.touch_last_synced(slug, now)
            tool_count = ToolRepository(conn).count_for_server(slug)
            return {
                'slug': slug, 'name': server['name'], 'endpoint': server['endpoint'],
                'toolCount': tool_count, 'trust': server['trust'], 'lastSynced': 'just now',
            }

    def _sync_real_tools(self, conn: sqlite3.Connection, *, slug: str, server: dict) -> None:
        """Discover the real server's tools (raises `McpDiscoveryError` on failure,
        mapped to 502 by the router), then register trust + a conservative
        default policy action for each newly-seen tool."""
        discovered = McpClient(server['endpoint']).discover_tools()

        tools_repo = ToolRepository(conn)
        trust_repo = TrustRepository(conn)
        tools_repo.delete_for_server(slug)

        tool_risks: dict[str, str] = {}
        trust_status = 'Verified' if server['trust'] == 'Trusted' else 'Needs approval'

        for tool in discovered:
            name = tool.get('name')
            if not name:
                continue
            risk = self._risk_classifier.classify(name)
            tool_risks[name] = risk
            input_schema = tool.get('inputSchema')
            tools_repo.add(
                server=slug, name=name, risk=risk, environment='Production',
                input_schema=json.dumps(input_schema) if input_schema else None,
            )
            trust_repo.upsert(
                tool_key=f'{slug}.{name}', publisher=server['name'], status=trust_status,
                hash_=f'sha256:{hashlib.sha256(json.dumps(tool, sort_keys=True).encode()).hexdigest()[:32]}',
            )

        if tool_risks:
            settings_repo = SettingsRepository(conn)
            merged_yaml = self._policy_engine.merge_default_actions(settings_repo.get('policy_yaml'), slug, tool_risks)
            settings_repo.set('policy_yaml', merged_yaml)
