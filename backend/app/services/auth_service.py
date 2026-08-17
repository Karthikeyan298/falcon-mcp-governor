from datetime import datetime, timedelta, timezone

from app.database import Database
from app.exceptions import BadRequestError, ConflictError, ForbiddenError, UnauthorizedError
from app.repositories import SessionRepository, UserRepository
from app.security import generate_session_token, generate_temp_password, hash_api_key, hash_password, verify_password

SESSION_TTL_HOURS = 24
SESSION_COOKIE_NAME = 'falcon_session'
MIN_PASSWORD_LENGTH = 8
_VALID_ROLES = ('admin', 'user')


class AuthService:
    """Server-side session auth: `login` issues an opaque token (the caller
    sets it as an HttpOnly cookie); only its SHA-256 hash is persisted, same
    pattern as agent API keys. `resolve_session` is what the auth middleware
    calls on every request."""

    def __init__(self, database: Database):
        self._database = database

    def login(self, *, username: str, password: str) -> tuple[str, dict]:
        with self._database.connect() as conn:
            user = UserRepository(conn).get_by_username(username)
            if user is None or not verify_password(password, user['password_hash']):
                raise UnauthorizedError('Invalid username or password')
            if user['status'] != 'Active':
                raise UnauthorizedError(f"User '{username}' is {user['status'].lower()}")

            token = generate_session_token()
            now = self._database.now_iso()
            expires_at = (datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)).isoformat()
            SessionRepository(conn).create(
                token_hash=hash_api_key(token), user_id=user['id'], created_at=now, expires_at=expires_at,
            )
            return token, self._public_user(user)

    def logout(self, token: str | None) -> None:
        if not token:
            return
        with self._database.connect() as conn:
            SessionRepository(conn).delete(hash_api_key(token))

    def resolve_session(self, token: str | None) -> dict | None:
        if not token:
            return None
        with self._database.connect() as conn:
            sessions = SessionRepository(conn)
            row = sessions.get_with_user(hash_api_key(token))
            if row is None:
                return None
            if row['expires_at'] < self._database.now_iso():
                sessions.delete(hash_api_key(token))
                return None
            if row['status'] != 'Active':
                return None
            return self._public_user(row)

    def create_user(self, *, requesting_user: dict, username: str, role: str) -> dict:
        if requesting_user['role'] != 'admin':
            raise ForbiddenError('Only admin users can create other users')
        if role not in _VALID_ROLES:
            raise BadRequestError(f"role must be one of {_VALID_ROLES}")

        with self._database.connect() as conn:
            repo = UserRepository(conn)
            if repo.exists(username):
                raise ConflictError('A user with this username already exists')

            temp_password = generate_temp_password()
            repo.create(
                username=username, password_hash=hash_password(temp_password),
                role=role, status='Active', created_at=self._database.now_iso(),
            )
            # temp_password is only ever returned here -- only its hash is persisted.
            return {'username': username, 'role': role, 'status': 'Active', 'temp_password': temp_password}

    def change_password(self, *, user_id: int, current_password: str, new_password: str) -> tuple[str, dict]:
        """Any logged-in user (including admin) can change their own
        password. Rotating the credential invalidates every session for this
        user -- including the one making this request -- and a fresh token
        is issued so the caller stays logged in here while any other
        device/session is signed out."""
        if len(new_password) < MIN_PASSWORD_LENGTH:
            raise BadRequestError(f'New password must be at least {MIN_PASSWORD_LENGTH} characters')

        with self._database.connect() as conn:
            users = UserRepository(conn)
            user = users.get(user_id)
            if user is None:
                raise UnauthorizedError('Not logged in')
            if not verify_password(current_password, user['password_hash']):
                raise UnauthorizedError('Current password is incorrect')

            users.set_password_hash(user_id, hash_password(new_password))

            sessions = SessionRepository(conn)
            sessions.delete_for_user(user_id)
            token = generate_session_token()
            now = self._database.now_iso()
            expires_at = (datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)).isoformat()
            sessions.create(token_hash=hash_api_key(token), user_id=user_id, created_at=now, expires_at=expires_at)

            return token, self._public_user(user)

    def list_users(self) -> list[dict]:
        with self._database.connect() as conn:
            return [self._public_user(u) for u in UserRepository(conn).list_all()]

    @staticmethod
    def _public_user(row: dict) -> dict:
        return {'id': row['id'], 'username': row['username'], 'role': row['role'], 'status': row['status']}
