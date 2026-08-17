from fastapi import APIRouter, Depends

from app.dependencies import get_tool_service
from app.services.tool_service import ToolService

router = APIRouter()


@router.get('/api/tools')
def list_tools(service: ToolService = Depends(get_tool_service)):
    return service.list_tools()
