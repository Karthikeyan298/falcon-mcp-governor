from fastapi import APIRouter, Depends

from app.dependencies import get_audit_service
from app.services.audit_service import AuditService

router = APIRouter()


@router.get('/api/audit')
def list_audit(service: AuditService = Depends(get_audit_service)):
    return service.list_audit()
