import json
from dataclasses import dataclass
from typing import Mapping

from app.database import Database
from app.exceptions import BadRequestError, NotFoundError, UnauthorizedError
from app.formatting import decision_label
from app.gateway_session import GatewaySessionStore
from app.mcp_client import McpClient
from app.policy_engine import InvalidPolicyError, PolicyEngine
from app.repositories import AgentRepository, ApprovalRepository, AuditRepository, ServerRepository, SettingsRepository, TrustRepository
from app.services.anomaly_service import AnomalyDetector
from app.security import hash_api_key


@dataclass
class McpGatewayResponse:
    """What a `/mcp/{slug}` call should send back, transport-agnostic.

    `payload=None` means a no-content response (e.g. 202/204); the router
    decides how to encode `payload` (SSE, in this app's case).
    """
    payload: dict | None
    session_id: str | None = None
    status_code: int = 200


class McpGatewayService:
    """The real MCP gateway: agents connect here (`/mcp/{slug}`) instead of a
    server's raw endpoint. Every `tools/call` -- and `tools/list`, for
    visibility -- runs through the policy engine before (if ever) reaching
    the real upstream MCP server."""

    def __init__(self, database: Database, policy_engine: PolicyEngine, session_store: GatewaySessionStore):
        self._database = database
        self._policy_engine = policy_engine
        self._session_store = session_store

    def handle_request(self, slug: str, body: dict, headers: Mapping[str, str]) -> McpGatewayResponse:
        method = body.get('method')
        req_id = body.get('id')
        params = body.get('params') or {}
        incoming_session_id = headers.get('mcp-session-id')

        with self._database.connect() as conn:
            server = ServerRepository(conn).get(slug)
            if server is None:
                raise NotFoundError('Unknown MCP server')

            endpoint = server['endpoint']
            if not endpoint.startswith(('http://', 'https://')):
                raise BadRequestError('This server has no live MCP endpoint to proxy to')

            if method == 'initialize':
                return self._handle_initialize(conn, slug, endpoint, params, req_id, headers)

            session = self._session_store.get(incoming_session_id, slug)
            if session is None:
                raise BadRequestError('Missing or unknown mcp-session-id; call initialize first')

            if method == 'notifications/initialized':
                McpClient(endpoint).notify_initialized(session.upstream_session_id)
                return McpGatewayResponse(payload=None, status_code=202)

            if method == 'tools/list':
                return self._handle_tools_list(conn, slug, endpoint, session, incoming_session_id, req_id)

            if method == 'tools/call':
                return self._handle_tools_call(conn, slug, endpoint, session, incoming_session_id, params, req_id)

            # transparent passthrough for anything else (resources/list, prompts/list, ping, ...)
            result = McpClient(endpoint).call(session.upstream_session_id, method, params, req_id=req_id)
            return McpGatewayResponse(payload=self._rpc_result(req_id, result), session_id=incoming_session_id)

    def open_stream(self, slug: str, session_id: str | None) -> None:
        """Validates a session for the optional GET server-push channel; raises BadRequestError if invalid."""
        if self._session_store.get(session_id, slug) is None:
            raise BadRequestError('Missing or unknown mcp-session-id; call initialize first')

    def close_session(self, session_id: str | None) -> None:
        self._session_store.close(session_id)

    def _handle_initialize(self, conn, slug: str, endpoint: str, params: dict, req_id, headers: Mapping[str, str]) -> McpGatewayResponse:
        # Agent identity comes from the `X-Agent-Key` header, not the self-reported
        # clientInfo.name -- any client could otherwise claim to be any agent and
        # inherit that agent's policy. The key is issued once at agent creation
        # (POST /api/agents) and only its hash is ever stored.
        api_key = headers.get('x-agent-key')
        if not api_key:
            raise UnauthorizedError('Missing X-Agent-Key header; agents must authenticate to use the gateway')

        agent = AgentRepository(conn).get_by_api_key_hash(hash_api_key(api_key))
        if agent is None:
            raise UnauthorizedError('Invalid agent API key')
        if agent['status'] != 'Active':
            raise UnauthorizedError(f"Agent '{agent['name']}' is {agent['status'].lower()}")

        agent_name = agent['name']
        user = headers.get('x-agent-user', agent_name)

        upstream_session_id, result = McpClient(endpoint).initialize_session()

        gateway_session_id = self._session_store.create(
            slug=slug, endpoint=endpoint, upstream_session_id=upstream_session_id, agent=agent_name, user=user,
        )
        return McpGatewayResponse(payload=self._rpc_result(req_id, result), session_id=gateway_session_id)

    def _handle_tools_list(self, conn, slug, endpoint, session, incoming_session_id, req_id) -> McpGatewayResponse:
        result = McpClient(endpoint).call(session.upstream_session_id, 'tools/list', {}, req_id=req_id)

        settings = SettingsRepository(conn)
        trust_repo = TrustRepository(conn)
        policy_yaml = settings.get('policy_yaml')

        visible_tools = []
        for tool in result.get('tools', []):
            name = tool.get('name')
            try:
                outcome = self._policy_engine.evaluate(
                    policy_yaml=policy_yaml, server=slug, tool=name, params={},
                    trust_status=trust_repo.get_status(f'{slug}.{name}'), agent=session.agent,
                )
            except InvalidPolicyError:
                outcome = None
            if outcome is None or outcome.decision != 'deny':
                visible_tools.append(tool)

        return McpGatewayResponse(
            payload=self._rpc_result(req_id, {'tools': visible_tools}), session_id=incoming_session_id,
        )

    def _handle_tools_call(self, conn, slug, endpoint, session, incoming_session_id, params, req_id) -> McpGatewayResponse:
        tool_name = params.get('name')
        arguments = params.get('arguments') or {}

        settings = SettingsRepository(conn)
        trust_repo = TrustRepository(conn)
        audit_repo = AuditRepository(conn)

        outcome = self._policy_engine.evaluate(
            policy_yaml=settings.get('policy_yaml'), server=slug, tool=tool_name, params=arguments,
            trust_status=trust_repo.get_status(f'{slug}.{tool_name}'), agent=session.agent,
        )  # InvalidPolicyError propagates -> 422 via router's exception handler

        label = decision_label(outcome.decision)
        now = self._database.now_iso()
        audit_repo.log(
            agent=session.agent, server=slug, tool=tool_name, action='invoke',
            decision=label, user=session.user, reason=outcome.reason, created_at=now,
        )

        AnomalyDetector(self._database).check_with_conn(
            conn, agent=session.agent, server=slug, tool=tool_name, decision=label, now=now,
        )

        if outcome.decision == 'require_approval':
            ApprovalRepository(conn).create(
                agent=session.agent, server=slug, tool=tool_name,
                arguments=json.dumps(arguments), user=session.user, created_at=now,
            )

        if outcome.decision in ('deny', 'require_approval'):
            return self._blocked_result(req_id, outcome.reason)

        result = McpClient(endpoint).call(
            session.upstream_session_id, 'tools/call', {'name': tool_name, 'arguments': arguments}, req_id=req_id,
        )
        return McpGatewayResponse(payload=self._rpc_result(req_id, result), session_id=incoming_session_id)

    @staticmethod
    def _rpc_result(req_id, result: dict) -> dict:
        return {'jsonrpc': '2.0', 'id': req_id, 'result': result}

    @classmethod
    def _blocked_result(cls, req_id, text: str) -> McpGatewayResponse:
        return McpGatewayResponse(payload=cls._rpc_result(req_id, {
            'content': [{'type': 'text', 'text': text}], 'isError': True,
        }))
