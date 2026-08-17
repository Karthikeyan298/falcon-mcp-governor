from fastapi import APIRouter, Depends

from app.dependencies import get_gateway_invoke_service
from app.schemas import GatewayInvokeRequest
from app.services.gateway_invoke_service import GatewayInvokeService

router = APIRouter()


@router.post('/api/gateway/invoke')
def gateway_invoke(request: GatewayInvokeRequest, service: GatewayInvokeService = Depends(get_gateway_invoke_service)):
    return service.invoke(agent=request.agent, server=request.server, tool=request.tool, user=request.user, params=request.params)
