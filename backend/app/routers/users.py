from fastapi import APIRouter, Depends

from app.dependencies import get_auth_service, require_admin
from app.schemas import UserCreate
from app.services.auth_service import AuthService

router = APIRouter()


@router.get('/api/users')
def list_users(_: dict = Depends(require_admin), auth_service: AuthService = Depends(get_auth_service)):
    return auth_service.list_users()


@router.post('/api/users')
def create_user(
    payload: UserCreate, requesting_user: dict = Depends(require_admin),
    auth_service: AuthService = Depends(get_auth_service),
):
    return auth_service.create_user(requesting_user=requesting_user, username=payload.username, role=payload.role)
