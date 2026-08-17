from fastapi import APIRouter, Depends

from app.dependencies import get_agent_service
from app.schemas import AgentCreate
from app.services.agent_service import AgentService

router = APIRouter()


@router.get('/api/agents')
def list_agents(service: AgentService = Depends(get_agent_service)):
    return service.list_agents()


@router.post('/api/agents')
def create_agent(payload: AgentCreate, service: AgentService = Depends(get_agent_service)):
    return service.register(
        name=payload.name, owner=payload.owner, environment=payload.environment,
        tools_allowed=payload.tools_allowed, status=payload.status,
    )


@router.delete('/api/agents/{name}')
def delete_agent(name: str, service: AgentService = Depends(get_agent_service)):
    service.remove(name)
    return {'status': 'deleted', 'name': name}


@router.post('/api/agents/{name}/toggle')
def toggle_agent(name: str, service: AgentService = Depends(get_agent_service)):
    return service.toggle_status(name)
