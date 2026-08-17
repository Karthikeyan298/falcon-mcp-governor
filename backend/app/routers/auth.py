from fastapi import APIRouter, Depends, Request, Response

from app.dependencies import get_auth_service, get_current_user
from app.schemas import ChangePasswordRequest, LoginRequest
from app.services.auth_service import SESSION_COOKIE_NAME, SESSION_TTL_HOURS, AuthService

router = APIRouter()


@router.post('/api/auth/login')
def login(payload: LoginRequest, response: Response, auth_service: AuthService = Depends(get_auth_service)):
    token, user = auth_service.login(username=payload.username, password=payload.password)
    response.set_cookie(
        key=SESSION_COOKIE_NAME, value=token, httponly=True, samesite='lax',
        max_age=SESSION_TTL_HOURS * 3600, path='/',
    )
    return user


@router.post('/api/auth/logout')
def logout(request: Request, response: Response, auth_service: AuthService = Depends(get_auth_service)):
    auth_service.logout(request.cookies.get(SESSION_COOKIE_NAME))
    response.delete_cookie(SESSION_COOKIE_NAME, path='/')
    return {'status': 'logged_out'}


@router.get('/api/auth/me')
def me(user: dict = Depends(get_current_user)):
    return user


@router.post('/api/auth/password')
def change_password(
    payload: ChangePasswordRequest, response: Response,
    user: dict = Depends(get_current_user), auth_service: AuthService = Depends(get_auth_service),
):
    token, updated_user = auth_service.change_password(
        user_id=user['id'], current_password=payload.current_password, new_password=payload.new_password,
    )
    response.set_cookie(
        key=SESSION_COOKIE_NAME, value=token, httponly=True, samesite='lax',
        max_age=SESSION_TTL_HOURS * 3600, path='/',
    )
    return updated_user
