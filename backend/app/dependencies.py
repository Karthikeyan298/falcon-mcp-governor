"""FastAPI dependency providers: wires repositories' shared singletons
(Database, PolicyEngine, GatewaySessionStore) into a fresh service instance
per request. Services are cheap, stateless wrappers, so building one per
request is simpler than trying to cache them."""

from fastapi import Depends, Request

from app.database import Database, get_database
from app.exceptions import ForbiddenError, UnauthorizedError
from app.gateway_session import GatewaySessionStore, get_session_store
from app.policy_engine import PolicyEngine, get_policy_engine
from app.services.agent_service import AgentService
from app.services.alert_service import AlertService
from app.services.approval_service import ApprovalService
from app.services.audit_service import AuditService
from app.services.auth_service import SESSION_COOKIE_NAME, AuthService
from app.services.dashboard_service import DashboardService
from app.services.gateway_invoke_service import GatewayInvokeService
from app.services.mcp_gateway_service import McpGatewayService
from app.services.policy_service import PolicyService
from app.services.server_service import ServerService
from app.services.tool_service import ToolService


def get_auth_service(database: Database = Depends(get_database)) -> AuthService:
    return AuthService(database)


def get_current_user(request: Request, auth_service: AuthService = Depends(get_auth_service)) -> dict:
    """Resolves the logged-in user from the session cookie. The auth
    middleware (see main.py) already ran this same check for every `/api/*`
    route and would have rejected the request if it failed -- this
    dependency exists so route handlers that need the user's identity/role
    (e.g. user creation) can get it via normal DI instead of `request.state`."""
    user = auth_service.resolve_session(request.cookies.get(SESSION_COOKIE_NAME))
    if user is None:
        raise UnauthorizedError('Not logged in')
    return user


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user['role'] != 'admin':
        raise ForbiddenError('Admin role required')
    return user


def get_dashboard_service(
    database: Database = Depends(get_database), policy_engine: PolicyEngine = Depends(get_policy_engine),
) -> DashboardService:
    return DashboardService(database, policy_engine)


def get_agent_service(
    database: Database = Depends(get_database), policy_engine: PolicyEngine = Depends(get_policy_engine),
) -> AgentService:
    return AgentService(database, policy_engine)


def get_server_service(
    database: Database = Depends(get_database), policy_engine: PolicyEngine = Depends(get_policy_engine),
) -> ServerService:
    return ServerService(database, policy_engine)


def get_policy_service(
    database: Database = Depends(get_database), policy_engine: PolicyEngine = Depends(get_policy_engine),
) -> PolicyService:
    return PolicyService(database, policy_engine)


def get_alert_service(database: Database = Depends(get_database)) -> AlertService:
    return AlertService(database)


def get_approval_service(
    database: Database = Depends(get_database), policy_engine: PolicyEngine = Depends(get_policy_engine),
) -> ApprovalService:
    return ApprovalService(database, policy_engine)


def get_audit_service(database: Database = Depends(get_database)) -> AuditService:
    return AuditService(database)


def get_tool_service(database: Database = Depends(get_database)) -> ToolService:
    return ToolService(database)


def get_gateway_invoke_service(
    database: Database = Depends(get_database), policy_engine: PolicyEngine = Depends(get_policy_engine),
) -> GatewayInvokeService:
    return GatewayInvokeService(database, policy_engine)


def get_mcp_gateway_service(
    database: Database = Depends(get_database),
    policy_engine: PolicyEngine = Depends(get_policy_engine),
    session_store: GatewaySessionStore = Depends(get_session_store),
) -> McpGatewayService:
    return McpGatewayService(database, policy_engine, session_store)
