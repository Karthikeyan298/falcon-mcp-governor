"""Pydantic request models for the REST API."""

from pydantic import BaseModel


class PolicyUpdate(BaseModel):
    yaml: str


class PolicyRuleUpsert(BaseModel):
    yaml: str
    agent: str | None = None  # None/empty -> applies to all agents
    server: str
    tool: str = '*'
    action: str


class PolicyParamRuleUpsert(BaseModel):
    yaml: str
    agent: str | None = None
    server: str
    tool: str
    param: str
    operator: str
    value: str
    decision: str = 'deny'
    reason: str = ''


class GatewayInvokeRequest(BaseModel):
    agent: str
    server: str
    tool: str
    user: str
    params: dict = {}


class ServerCreate(BaseModel):
    slug: str
    name: str
    endpoint: str
    trust: str = 'Needs review'


class ServerUpdate(BaseModel):
    name: str
    endpoint: str
    trust: str


class AgentCreate(BaseModel):
    name: str
    owner: str
    environment: str = 'Production'
    tools_allowed: int = 0
    status: str = 'Active'


class LoginRequest(BaseModel):
    username: str
    password: str


class UserCreate(BaseModel):
    username: str
    role: str = 'user'


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
