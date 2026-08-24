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


class CredentialConfig(BaseModel):
    type: str = 'none'           # none | bearer | api_key | basic
    token: str = ''              # bearer
    header_name: str = 'X-Api-Key'  # api_key
    header_value: str = ''       # api_key
    username: str = ''           # basic
    password: str = ''           # basic


class ServerCreate(BaseModel):
    slug: str
    name: str
    endpoint: str
    trust: str = 'Needs review'
    credential: CredentialConfig | None = None


class ServerUpdate(BaseModel):
    name: str
    endpoint: str
    trust: str
    credential: CredentialConfig | None = None


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
