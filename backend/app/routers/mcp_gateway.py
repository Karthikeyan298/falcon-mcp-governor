"""HTTP transport for the real MCP gateway proxy: encodes `McpGatewayService`
results as the streamable-HTTP/SSE responses the MCP protocol expects. All
policy/session/proxying logic lives in the service -- this module only knows
about HTTP.
"""

import json

from fastapi import APIRouter, Depends, Request, Response

from app.dependencies import get_mcp_gateway_service
from app.exceptions import BadRequestError, NotFoundError, UnauthorizedError
from app.mcp_client import McpDiscoveryError
from app.services.mcp_gateway_service import McpGatewayResponse, McpGatewayService

router = APIRouter()

# JSON-RPC error codes for gateway-level failures.
# -32001 / -32002 are in the implementation-defined range (-32099 to -32000).
_JSONRPC_UNAUTHORIZED = -32001
_JSONRPC_NOT_FOUND = -32002
_JSONRPC_INVALID_REQUEST = -32600
_JSONRPC_INTERNAL = -32603


def _to_http_response(result: McpGatewayResponse) -> Response:
    headers = {'mcp-session-id': result.session_id} if result.session_id else {}
    if result.payload is None:
        return Response(status_code=result.status_code, headers=headers)
    return Response(
        content=f'event: message\ndata: {json.dumps(result.payload)}\n\n',
        media_type='text/event-stream',
        headers=headers,
        status_code=result.status_code,
    )


def _error_response(req_id, code: int, message: str, http_status: int) -> Response:
    """Return a JSON-RPC error as an SSE event so MCP clients can parse it."""
    payload = {'jsonrpc': '2.0', 'id': req_id, 'error': {'code': code, 'message': message}}
    return Response(
        content=f'event: message\ndata: {json.dumps(payload)}\n\n',
        media_type='text/event-stream',
        status_code=http_status,
    )


@router.post('/mcp/{slug}')
async def mcp_gateway(slug: str, request: Request, service: McpGatewayService = Depends(get_mcp_gateway_service)):
    body = await request.json()
    req_id = body.get('id')
    try:
        result = service.handle_request(slug, body, request.headers)
        return _to_http_response(result)
    except UnauthorizedError as exc:
        return _error_response(req_id, _JSONRPC_UNAUTHORIZED, str(exc), 401)
    except (BadRequestError, NotFoundError) as exc:
        return _error_response(req_id, _JSONRPC_INVALID_REQUEST, str(exc), 400)
    except McpDiscoveryError:
        return _error_response(req_id, _JSONRPC_INTERNAL, 'Upstream service error.', 502)


@router.get('/mcp/{slug}')
def mcp_gateway_stream(slug: str, request: Request, service: McpGatewayService = Depends(get_mcp_gateway_service)):
    """Optional server-push channel. None of the proxied servers advertise
    listChanged capabilities, so there's nothing to push; open (and
    immediately end) an empty SSE stream so spec-compliant clients that
    expect this channel don't treat it as an error."""
    service.open_stream(slug, request.headers.get('mcp-session-id'))
    return Response(content='', media_type='text/event-stream')


@router.delete('/mcp/{slug}')
def mcp_gateway_close(slug: str, request: Request, service: McpGatewayService = Depends(get_mcp_gateway_service)):
    service.close_session(request.headers.get('mcp-session-id'))
    return Response(status_code=204)
