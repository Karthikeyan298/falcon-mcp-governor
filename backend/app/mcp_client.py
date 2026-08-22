"""MCP client for the streamable-HTTP transport.

Speaks just enough of the protocol (initialize -> notifications/initialized ->
tools/list / tools/call / ...) to (a) sync a real MCP server's tool list into
the control plane's local registry, and (b) proxy real agent traffic through
the governance gateway. Deliberately hand-rolled with httpx instead of the
official `mcp` SDK, whose latest release pulls in a starlette/pydantic version
that conflicts with this project's pinned FastAPI.

The streamable-HTTP transport is stateless at the connection level -- session
continuity is carried entirely by the `mcp-session-id` header, so every call
here opens a fresh short-lived HTTP request rather than holding a socket open.
"""

import json

import httpx

PROTOCOL_VERSION = '2024-11-05'
_DEFAULT_CLIENT_INFO = {'name': 'mcp-control-plane', 'version': '0.1.0'}


class McpDiscoveryError(Exception):
    pass


class McpClient:
    def __init__(self, endpoint: str, *, client_info: dict | None = None):
        self._endpoint = endpoint
        self._client_info = client_info or _DEFAULT_CLIENT_INFO
        self._headers = {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream'}

    def initialize_session(self, timeout: float = 5.0) -> tuple[str | None, dict]:
        """Perform the initialize handshake and complete it with notifications/initialized.

        Returns (session_id, initialize result payload).
        """
        resp = self._post(
            {
                'jsonrpc': '2.0',
                'id': 1,
                'method': 'initialize',
                'params': {
                    'protocolVersion': PROTOCOL_VERSION,
                    'capabilities': {},
                    'clientInfo': self._client_info,
                },
            },
            self._headers,
            timeout,
        )
        payload = self._parse_response(resp)
        if 'error' in payload:
            raise McpDiscoveryError(payload['error'].get('message', 'initialize failed'))

        session_id = resp.headers.get('mcp-session-id')
        self.notify_initialized(session_id, timeout)

        return session_id, payload.get('result', {})

    def notify_initialized(self, session_id: str | None, timeout: float = 5.0) -> None:
        self._post({'jsonrpc': '2.0', 'method': 'notifications/initialized'}, self._session_headers(session_id), timeout)

    def call(self, session_id: str | None, method: str, params: dict, req_id, timeout: float = 10.0) -> dict:
        """Send a JSON-RPC request against an established session and return its `result`."""
        body = {'jsonrpc': '2.0', 'id': req_id, 'method': method, 'params': params}
        resp = self._post(body, self._session_headers(session_id), timeout)
        payload = self._parse_response(resp)
        if 'error' in payload:
            raise McpDiscoveryError(payload['error'].get('message', f'{method} failed'))
        return payload.get('result', {})

    def discover_tools(self, timeout: float = 5.0) -> list[dict]:
        """Connect to the MCP server and return its tool list via tools/list."""
        session_id, _ = self.initialize_session(timeout)
        result = self.call(session_id, 'tools/list', {}, req_id=2, timeout=timeout)
        return result.get('tools', [])

    def _session_headers(self, session_id: str | None) -> dict:
        headers = dict(self._headers)
        if session_id:
            headers['mcp-session-id'] = session_id
        return headers

    def _post(self, body: dict, headers: dict, timeout: float) -> httpx.Response:
        try:
            resp = httpx.post(self._endpoint, json=body, headers=headers, timeout=timeout)
            resp.raise_for_status()
            return resp
        except httpx.HTTPError as exc:
            raise McpDiscoveryError(f'Could not reach MCP server at {self._endpoint}: {exc}') from exc

    @staticmethod
    def _parse_response(resp: httpx.Response) -> dict:
        content_type = resp.headers.get('content-type', '')
        if 'text/event-stream' in content_type:
            for line in resp.text.splitlines():
                if line.startswith('data:'):
                    return json.loads(line[len('data:'):].strip())
            raise McpDiscoveryError('No data event in SSE response')
        return resp.json()
