"""HTTP transport for the real MCP gateway proxy: encodes `McpGatewayService`
results as the streamable-HTTP/SSE responses the MCP protocol expects. All
policy/session/proxying logic lives in the service -- this module only knows
about HTTP.
"""

import json

from fastapi import APIRouter, Depends, Request, Response

from app.dependencies import get_mcp_gateway_service
from app.services.mcp_gateway_service import McpGatewayResponse, McpGatewayService

router = APIRouter()


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


@router.post('/mcp/{slug}')
async def mcp_gateway(slug: str, request: Request, service: McpGatewayService = Depends(get_mcp_gateway_service)):
    body = await request.json()
    result = service.handle_request(slug, body, request.headers)
    return _to_http_response(result)


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
