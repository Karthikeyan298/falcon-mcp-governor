from app.database import Database
from app.exceptions import ConflictError, NotFoundError
from app.policy_engine import InvalidPolicyError, PolicyEngine
from app.repositories import AgentRepository, SettingsRepository, ToolRepository, TrustRepository
from app.security import generate_api_key


class AgentService:
    def __init__(self, database: Database, policy_engine: PolicyEngine):
        self._database = database
        self._policy_engine = policy_engine

    def list_agents(self) -> list[dict]:
        with self._database.connect() as conn:
            agents = AgentRepository(conn).list_all()
            tools = ToolRepository(conn).list_all()
            policy_yaml = SettingsRepository(conn).get('policy_yaml')
            trust_repo = TrustRepository(conn)

            for agent in agents:
                agent.pop('api_key_hash', None)
                count = 0
                for tool in tools:
                    try:
                        outcome = self._policy_engine.evaluate(
                            policy_yaml=policy_yaml,
                            server=tool['server'],
                            tool=tool['name'],
                            params={},
                            trust_status=trust_repo.get_status(f"{tool['server']}.{tool['name']}"),
                            agent=agent['name'],
                        )
                        if outcome.decision != 'deny':
                            count += 1
                    except InvalidPolicyError:
                        pass
                agent['tools_allowed'] = count

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
