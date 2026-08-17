from app.database import Database
from app.exceptions import ConflictError, NotFoundError
from app.repositories import AgentRepository
from app.security import generate_api_key


class AgentService:
    def __init__(self, database: Database):
        self._database = database

    def list_agents(self) -> list[dict]:
        with self._database.connect() as conn:
            agents = AgentRepository(conn).list_all()
            for agent in agents:
                agent.pop('api_key_hash', None)
            return agents

    def register(self, *, name: str, owner: str, environment: str, tools_allowed: int, status: str) -> dict:
        with self._database.connect() as conn:
            repo = AgentRepository(conn)
            if repo.exists(name):
                raise ConflictError('An agent with this name already exists')
            api_key, api_key_hash = generate_api_key()
            repo.create(
                name=name, owner=owner, environment=environment, tools_allowed=tools_allowed,
                status=status, api_key_hash=api_key_hash,
            )
            # api_key is only ever returned here -- only the hash is persisted, so
            # this is the caller's one chance to see it (e.g. to put in the agent's config).
            return {
                'name': name, 'owner': owner, 'environment': environment,
                'tools_allowed': tools_allowed, 'status': status, 'api_key': api_key,
            }

    def remove(self, name: str) -> None:
        with self._database.connect() as conn:
            repo = AgentRepository(conn)
            if not repo.exists(name):
                raise NotFoundError('Agent not found')
            repo.delete(name)

    def toggle_status(self, name: str) -> dict:
        with self._database.connect() as conn:
            repo = AgentRepository(conn)
            agent = repo.get(name)
            if agent is None:
                raise NotFoundError('Agent not found')
            new_status = 'Suspended' if agent['status'] == 'Active' else 'Active'
            repo.set_status(name, new_status)
            agent.pop('api_key_hash', None)
            return {**agent, 'status': new_status}
