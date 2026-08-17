from fastapi import APIRouter, Depends

from app.dependencies import get_server_service
from app.schemas import ServerCreate, ServerUpdate
from app.services.server_service import ServerService

router = APIRouter()


@router.get('/api/servers')
def list_servers(service: ServerService = Depends(get_server_service)):
    return service.list_servers()


@router.post('/api/servers')
def create_server(payload: ServerCreate, service: ServerService = Depends(get_server_service)):
    return service.create(slug=payload.slug, name=payload.name, endpoint=payload.endpoint, trust=payload.trust)


@router.put('/api/servers/{slug}')
def update_server(slug: str, payload: ServerUpdate, service: ServerService = Depends(get_server_service)):
    return service.update(slug, name=payload.name, endpoint=payload.endpoint, trust=payload.trust)


@router.delete('/api/servers/{slug}')
def delete_server(slug: str, service: ServerService = Depends(get_server_service)):
    service.delete(slug)
    return {'status': 'deleted', 'slug': slug}


@router.post('/api/servers/{slug}/sync')
def sync_server(slug: str, service: ServerService = Depends(get_server_service)):
    return service.sync(slug)
