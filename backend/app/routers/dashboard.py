from fastapi import APIRouter, Depends

from app.dependencies import get_dashboard_service
from app.services.dashboard_service import DashboardService

router = APIRouter()


@router.get('/health')
def health_check():
    return {'status': 'ok'}


@router.get('/api/dashboard')
def dashboard(service: DashboardService = Depends(get_dashboard_service)):
    return service.get_dashboard()
