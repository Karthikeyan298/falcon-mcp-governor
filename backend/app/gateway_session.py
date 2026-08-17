"""In-memory session registry for the real MCP gateway proxy (`/mcp/{slug}`).

Sessions live only for the process's lifetime -- restarting the backend
drops any agent's in-flight session, same as before this rewrite. Wrapping
the raw dict in a class stops session bookkeeping (create/lookup/close, plus
the slug-match check) from being reimplemented ad hoc at each call site.
"""

import uuid
from dataclasses import dataclass


@dataclass
class GatewaySession:
    slug: str
    endpoint: str
    upstream_session_id: str | None
    agent: str
    user: str


class GatewaySessionStore:
    def __init__(self):
        self._sessions: dict[str, GatewaySession] = {}

    def create(self, *, slug: str, endpoint: str, upstream_session_id: str | None, agent: str, user: str) -> str:
        session_id = uuid.uuid4().hex
        self._sessions[session_id] = GatewaySession(
            slug=slug, endpoint=endpoint, upstream_session_id=upstream_session_id, agent=agent, user=user,
        )
        return session_id

    def get(self, session_id: str | None, slug: str) -> GatewaySession | None:
        session = self._sessions.get(session_id or '')
        if session is None or session.slug != slug:
            return None
        return session

    def close(self, session_id: str | None) -> None:
        self._sessions.pop(session_id or '', None)


_default_session_store = GatewaySessionStore()


def get_session_store() -> GatewaySessionStore:
    """FastAPI dependency provider; one shared store for the app's lifetime."""
    return _default_session_store
