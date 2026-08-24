import hashlib
import json
import logging
import sqlite3

from app.database import Database
from app.exceptions import ConflictError, NotFoundError
from app.formatting import relative_time
from app.mcp_client import McpClient
from app.policy_engine import PolicyEngine
from app.repositories import ServerRepository, SettingsRepository, ToolRepository, TrustRepository
from app.security import decrypt_credential, encrypt_credential

logger = logging.getLogger(__name__)


def _stored_auth_type(server: dict) -> str:
    """Return the auth type label for display — never exposes the credential value."""
    raw = server.get('credentials')
    if not raw:
        return 'none'
    try:
        cred = json.loads(decrypt_credential(raw))
        return cred.get('type', 'none')
    except Exception:
        return 'none'


def _auth_headers(server: dict) -> dict:
    """Decrypt a server's stored credentials and return the corresponding HTTP headers.

    Returns an empty dict when no credentials are configured or decryption fails
    (logged as a warning so a misconfigured server doesn't crash an unrelated call).
    """
    raw = server.get('credentials')
    if not raw:
        return {}
    try:
        cred = json.loads(decrypt_credential(raw))
    except Exception:
        logger.warning('Failed to decrypt credentials for server %s — skipping auth headers', server.get('slug'))
        return {}

    ctype = cred.get('type', 'none')
    if ctype == 'bearer':
        token = cred.get('token', '')
        return {'Authorization': f'Bearer {token}'} if token else {}
    if ctype == 'api_key':
        header = cred.get('header_name', 'X-Api-Key')
        value = cred.get('header_value', '')
        return {header: value} if value else {}
    if ctype == 'basic':
        import base64
        username = cred.get('username', '')
        password = cred.get('password', '')
        encoded = base64.b64encode(f'{username}:{password}'.encode()).decode()
        return {'Authorization': f'Basic {encoded}'} if username else {}
    return {}


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
                    'authType': _stored_auth_type(s),
                }
                for s in servers_repo.list_all()
            ]

    def create(self, *, slug: str, name: str, endpoint: str, trust: str, credential: dict | None = None) -> dict:
        with self._database.connect() as conn:
            repo = ServerRepository(conn)
            if repo.exists(slug):
                raise ConflictError('A server with this slug already exists')
            encrypted = encrypt_credential(json.dumps(credential)) if credential and credential.get('type', 'none') != 'none' else None
            repo.create(slug=slug, name=name, endpoint=endpoint, trust=trust, last_synced=self._database.now_iso(), credentials=encrypted)
            return {'slug': slug, 'name': name, 'endpoint': endpoint, 'toolCount': 0, 'trust': trust, 'lastSynced': 'just now', 'authType': credential.get('type', 'none') if credential else 'none'}

    def update(self, slug: str, *, name: str, endpoint: str, trust: str, credential: dict | None = None) -> dict:
        with self._database.connect() as conn:
            repo = ServerRepository(conn)
            server = repo.get(slug)
            if server is None:
                raise NotFoundError('Server not found')
            encrypted = encrypt_credential(json.dumps(credential)) if credential and credential.get('type', 'none') != 'none' else None
            repo.update(slug, name=name, endpoint=endpoint, trust=trust, credentials=encrypted)
            tool_count = ToolRepository(conn).count_for_server(slug)
            return {
                'slug': slug, 'name': name, 'endpoint': endpoint, 'toolCount': tool_count,
                'trust': trust, 'lastSynced': relative_time(server['last_synced']),
                'authType': credential.get('type', 'none') if credential else 'none',
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
                self._sync_real_tools(conn, slug=slug, server=servers_repo.get(slug))

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
        discovered = McpClient(server['endpoint'], extra_headers=_auth_headers(server)).discover_tools()

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
