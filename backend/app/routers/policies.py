from fastapi import APIRouter, Depends, Query

from app.dependencies import get_policy_service
from app.schemas import PolicyParamRuleUpsert, PolicyRuleUpsert, PolicyUpdate
from app.services.policy_service import PolicyService

router = APIRouter()


@router.get('/api/policies/tool-matrix')
def tool_matrix(
    agent: str | None = Query(default=None),
    service: PolicyService = Depends(get_policy_service),
):
    return service.tool_matrix(agent)


@router.get('/api/policy')
def get_policy(service: PolicyService = Depends(get_policy_service)):
    return service.get_policy()


@router.post('/api/policies/rule-preview')
def preview_policy_rule(payload: PolicyRuleUpsert, service: PolicyService = Depends(get_policy_service)):
    merged_yaml = service.preview_rule(
        yaml_text=payload.yaml, agent=payload.agent, server=payload.server, tool=payload.tool, action=payload.action,
    )
    return {'yaml': merged_yaml}


@router.post('/api/policies/param-rule-preview')
def preview_param_rule(payload: PolicyParamRuleUpsert, service: PolicyService = Depends(get_policy_service)):
    merged_yaml = service.preview_param_rule(
        yaml_text=payload.yaml, agent=payload.agent, server=payload.server, tool=payload.tool,
        param=payload.param, operator=payload.operator, value=payload.value,
        decision=payload.decision, reason=payload.reason,
    )
    return {'yaml': merged_yaml}


@router.post('/api/policies/deploy')
def deploy_policy(payload: PolicyUpdate | None = None, service: PolicyService = Depends(get_policy_service)):
    service.deploy(payload.yaml if payload is not None else None)
    return {'status': 'deployed', 'lastDeployment': 'just now'}
