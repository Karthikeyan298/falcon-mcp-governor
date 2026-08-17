"""Domain-level exceptions.

Services raise these without knowing about HTTP; `main.py` registers one
exception handler per type to map them to status codes. This keeps HTTP
concerns out of the service/repository layers.
"""


class NotFoundError(Exception):
    """A requested entity (agent, server, tool, approval, ...) does not exist."""


class ConflictError(Exception):
    """The requested change conflicts with existing state (e.g. duplicate key)."""


class BadRequestError(Exception):
    """The request itself is invalid independent of any specific entity (e.g. missing MCP session)."""


class UnauthorizedError(Exception):
    """The request's credentials (e.g. agent API key, session cookie) are missing or invalid."""


class ForbiddenError(Exception):
    """The request is authenticated but lacks permission for this action (e.g. non-admin creating a user)."""
