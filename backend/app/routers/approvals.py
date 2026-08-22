from fastapi import APIRouter, Depends

from app.dependencies import get_approval_service, get_current_user
from app.services.approval_service import ApprovalService

router = APIRouter()


@router.get('/api/approvals')
def list_approvals(service: ApprovalService = Depends(get_approval_service)):
    return service.list_approvals()


@router.get('/api/approvals/pending-count')
def pending_count(service: ApprovalService = Depends(get_approval_service)):
    return {'count': service.count_pending()}


@router.post('/api/approvals/{approval_id}/approve')
def approve(
    approval_id: int,
    service: ApprovalService = Depends(get_approval_service),
    user: dict = Depends(get_current_user),
):
    return service.approve(approval_id, user['username'])


@router.post('/api/approvals/{approval_id}/deny')
def deny(
    approval_id: int,
    service: ApprovalService = Depends(get_approval_service),
    user: dict = Depends(get_current_user),
):
    return service.deny(approval_id, user['username'])
