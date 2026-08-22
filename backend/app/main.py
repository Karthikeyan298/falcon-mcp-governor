"""Application entry point.

Everything behavioral lives in `services/` (business logic, raising domain
exceptions from `exceptions.py`/`policy_engine.py`/`mcp_client.py`) and
`repositories.py` (SQL). This module only assembles the FastAPI app: CORS,
startup schema init, mapping domain exceptions to HTTP status codes, and
registering routers. See `routers/` for one module per resource area.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from fastapi.responses import JSONResponse

from app.database import get_database
from app.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError, UnauthorizedError
from app.mcp_client import McpDiscoveryError
from app.policy_engine import InvalidPolicyError
from app.routers import agents, approvals, audit, auth, dashboard, gateway, mcp_gateway, policies, servers, tools, users
from app.services.auth_service import SESSION_COOKIE_NAME, AuthService


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Resolve through dependency_overrides (not a bare get_database() call) so
    # tests that override get_database with an isolated DB get their schema
    # initialized too, instead of silently touching the real default DB file.
    database = app.dependency_overrides.get(get_database, get_database)()
    database.init_schema()
    yield


app = FastAPI(title='Falcon | MCP Governance API', lifespan=lifespan)

# CORS: `allow_origins=['*']` is invalid together with `allow_credentials=True`
# (browsers refuse to expose the response) -- login relies on a credentialed
# cookie, so this must be an explicit origin list. Override via env var if the
# UI is served from somewhere other than the default Angular dev server port.
_allowed_origins = os.environ.get('FALCON_UI_ORIGINS', 'http://localhost:4200').split(',')

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


# ---------------------------------------------------------------------------
# auth: every /api/* route except /api/auth/* requires a logged-in session.
# /health, /mcp/* (agent-key auth, not human login), and the docs are public.
# ---------------------------------------------------------------------------

@app.middleware('http')
async def require_login(request: Request, call_next):
    path = request.url.path
    # CORS preflight (OPTIONS) must reach CORSMiddleware unauthenticated --
    # @app.middleware('http') registers as outermost, ahead of add_middleware
    # calls, so this handler sees preflight requests before CORS does.
    if request.method != 'OPTIONS' and path.startswith('/api') and not path.startswith('/api/auth'):
        database = app.dependency_overrides.get(get_database, get_database)()
        user = AuthService(database).resolve_session(request.cookies.get(SESSION_COOKIE_NAME))
        if user is None:
            return JSONResponse(status_code=401, content={'detail': 'Not logged in'})
        request.state.user = user

    return await call_next(request)


# ---------------------------------------------------------------------------
# domain exception -> HTTP status mapping
# ---------------------------------------------------------------------------

def _error_response(status_code: int, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={'detail': str(exc)})


@app.exception_handler(NotFoundError)
async def handle_not_found(_: Request, exc: NotFoundError):
    return _error_response(404, exc)


@app.exception_handler(ConflictError)
async def handle_conflict(_: Request, exc: ConflictError):
    return _error_response(409, exc)


@app.exception_handler(BadRequestError)
async def handle_bad_request(_: Request, exc: BadRequestError):
    return _error_response(400, exc)


@app.exception_handler(UnauthorizedError)
async def handle_unauthorized(_: Request, exc: UnauthorizedError):
    return _error_response(401, exc)


@app.exception_handler(ForbiddenError)
async def handle_forbidden(_: Request, exc: ForbiddenError):
    return _error_response(403, exc)


@app.exception_handler(InvalidPolicyError)
async def handle_invalid_policy(_: Request, exc: InvalidPolicyError):
    return _error_response(422, exc)


@app.exception_handler(McpDiscoveryError)
async def handle_mcp_discovery_error(_: Request, exc: McpDiscoveryError):
    return _error_response(502, exc)


# ---------------------------------------------------------------------------
# routers
# ---------------------------------------------------------------------------

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(dashboard.router)
app.include_router(agents.router)
app.include_router(servers.router)
app.include_router(policies.router)
app.include_router(approvals.router)
app.include_router(audit.router)
app.include_router(tools.router)
app.include_router(gateway.router)
app.include_router(mcp_gateway.router)
