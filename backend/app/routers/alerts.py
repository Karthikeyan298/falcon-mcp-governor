from fastapi import APIRouter, Depends

from app.dependencies import get_alert_service, get_current_user, require_admin
from app.services.alert_service import AlertService

router = APIRouter()


@router.get('/api/alerts')
def list_alerts(service: AlertService = Depends(get_alert_service), _=Depends(get_current_user)):
    return service.list_alerts()


@router.get('/api/alerts/unacknowledged-count')
def unacknowledged_count(service: AlertService = Depends(get_alert_service), _=Depends(get_current_user)):
    return {'count': service.count_unacknowledged()}


@router.post('/api/alerts/{alert_id}/acknowledge')
def acknowledge_alert(alert_id: int, service: AlertService = Depends(get_alert_service), user=Depends(get_current_user)):
    return service.acknowledge(alert_id, user['username'])


@router.get('/api/alert-rules')
def get_rules(service: AlertService = Depends(get_alert_service), _=Depends(get_current_user)):
    return service.get_rules()


@router.put('/api/alert-rules')
def update_rules(rules: dict, service: AlertService = Depends(get_alert_service), _=Depends(require_admin)):
    return service.update_rules(rules)
