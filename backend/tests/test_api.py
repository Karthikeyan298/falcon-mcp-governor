import pytest
from fastapi.testclient import TestClient

from app.database import Database, get_database
from app.repositories import AgentRepository, ServerRepository, ToolRepository, TrustRepository, UserRepository
from app.security import hash_api_key, hash_password

TEST_ADMIN_USERNAME = 'test-admin'
TEST_ADMIN_PASSWORD = 'test-admin-pass'


def _seed_test_data(database: Database) -> None:
    """The app no longer ships demo data (see database.py), so tests that
    need agents/servers/tools/trust in place build their own minimal
    fixture directly through the repositories."""
    with database.connect() as conn:
        AgentRepository(conn).create(
            name='production-support', owner='alice', environment='Production',
            tools_allowed=6, status='Active', api_key_hash=hash_api_key('test-key'),
        )
        AgentRepository(conn).create(
            name='ops-agent', owner='bob', environment='Production',
            tools_allowed=3, status='Active', api_key_hash=hash_api_key('test-key-2'),
        )

        now = database.now_iso()
        servers_repo = ServerRepository(conn)
        servers_repo.create(slug='jira', name='Jira MCP', endpoint='mcp://jira.internal:7443', trust='Trusted', last_synced=now)
        servers_repo.create(slug='email', name='Email MCP', endpoint='mcp://email.internal:7443', trust='Trusted', last_synced=now)
        servers_repo.create(slug='kubernetes', name='Kubernetes MCP', endpoint='mcp://k8s.internal:7443', trust='Needs review', last_synced=now)

        tools_repo = ToolRepository(conn)
        trust_repo = TrustRepository(conn)
        for server, name, risk, status in [
            ('jira', 'search_issues', 'Low', 'Verified'),
            ('email', 'send_email', 'Medium', 'Needs approval'),
            ('kubernetes', 'delete_pod', 'High', 'Revoked'),
        ]:
            tools_repo.add(server=server, name=name, risk=risk, environment='Production')
            trust_repo.upsert(tool_key=f'{server}.{name}', publisher='Test', status=status, hash_='sha256:test')

        # A known-password admin, separate from the auto-bootstrapped 'admin'
        # user (whose random password isn't retrievable in tests), so tests
        # can log in and exercise the now-required auth on every /api/* route.
        UserRepository(conn).create(
            username=TEST_ADMIN_USERNAME, password_hash=hash_password(TEST_ADMIN_PASSWORD),
            role='admin', status='Active', created_at=now,
        )


@pytest.fixture
def client(tmp_path):
    from app.main import app

    database = Database(tmp_path / 'test.db')
    app.dependency_overrides[get_database] = lambda: database

    with TestClient(app) as c:
        _seed_test_data(database)
        login = c.post('/api/auth/login', json={'username': TEST_ADMIN_USERNAME, 'password': TEST_ADMIN_PASSWORD})
        assert login.status_code == 200, login.text
        yield c

    app.dependency_overrides.clear()


def test_health_endpoint(client):
    response = client.get('/health')

    assert response.status_code == 200
    assert response.json()['status'] == 'ok'


def test_dashboard_payload(client):
    response = client.get('/api/dashboard')

    assert response.status_code == 200
    payload = response.json()
    assert 'stats' in payload
    assert 'toolPolicies' in payload
    assert 'auditTrail' in payload
    assert 'signedTools' in payload
    assert 'policyYaml' in payload


def test_gateway_invoke_allow(client):
    response = client.post('/api/gateway/invoke', json={
        'agent': 'production-support',
        'server': 'jira',
        'tool': 'search_issues',
        'user': 'alice',
        'params': {},
    })

    assert response.status_code == 200
    payload = response.json()
    assert payload['decision'] == 'allow'
    assert payload['result']['ok'] is True


def test_gateway_invoke_deny_revoked_tool(client):
    response = client.post('/api/gateway/invoke', json={
        'agent': 'ops-agent',
        'server': 'kubernetes',
        'tool': 'delete_pod',
        'user': 'bob',
        'params': {'namespace': 'staging'},
    })

    assert response.status_code == 200
    payload = response.json()
    assert payload['decision'] == 'deny'


def test_gateway_invoke_deny_for_external_email(client):
    response = client.post('/api/gateway/invoke', json={
        'agent': 'production-support',
        'server': 'email',
        'tool': 'send_email',
        'user': 'alice',
        'params': {'recipient': 'external@gmail.com'},
    })

    assert response.status_code == 200
    payload = response.json()
    assert payload['decision'] == 'deny'
    assert payload['reason'] == 'External recipient blocked'


def test_deploy_policy_rejects_invalid_yaml(client):
    response = client.post('/api/policies/deploy', json={'yaml': 'not: valid: yaml: -'})
    assert response.status_code == 422


def test_api_requires_login(client):
    anonymous = TestClient(client.app)
    response = anonymous.get('/api/agents')
    assert response.status_code == 401


def test_login_wrong_password_rejected(client):
    anonymous = TestClient(client.app)
    response = anonymous.post('/api/auth/login', json={'username': TEST_ADMIN_USERNAME, 'password': 'wrong'})
    assert response.status_code == 401


def test_change_password_wrong_current_password_rejected(client):
    response = client.post('/api/auth/password', json={'current_password': 'wrong', 'new_password': 'new-strong-pass'})
    assert response.status_code == 401


def test_change_password_too_short_rejected(client):
    response = client.post('/api/auth/password', json={'current_password': TEST_ADMIN_PASSWORD, 'new_password': 'short'})
    assert response.status_code == 400


def test_change_password_then_login_with_new_password(client):
    response = client.post(
        '/api/auth/password', json={'current_password': TEST_ADMIN_PASSWORD, 'new_password': 'a-new-stronger-pass'},
    )
    assert response.status_code == 200
    # the change-password response itself rotates the session cookie, so this client is still logged in
    assert client.get('/api/agents').status_code == 200

    # the old password no longer works, the new one does, from a fresh client/session
    fresh = TestClient(client.app)
    old_login = fresh.post('/api/auth/login', json={'username': TEST_ADMIN_USERNAME, 'password': TEST_ADMIN_PASSWORD})
    assert old_login.status_code == 401

    new_login = fresh.post('/api/auth/login', json={'username': TEST_ADMIN_USERNAME, 'password': 'a-new-stronger-pass'})
    assert new_login.status_code == 200


def test_admin_can_create_user_and_non_admin_cannot(client):
    created = client.post('/api/users', json={'username': 'ops-viewer', 'role': 'user'})
    assert created.status_code == 200
    payload = created.json()
    assert payload['username'] == 'ops-viewer'
    assert payload['role'] == 'user'
    assert payload['temp_password']

    # log in as the newly-created non-admin user and confirm they're blocked from creating others
    non_admin = TestClient(client.app)
    login = non_admin.post('/api/auth/login', json={'username': 'ops-viewer', 'password': payload['temp_password']})
    assert login.status_code == 200

    forbidden = non_admin.post('/api/users', json={'username': 'someone-else', 'role': 'user'})
    assert forbidden.status_code == 403


def test_agents_and_servers_endpoints(client):
    agents = client.get('/api/agents').json()
    assert len(agents) > 0

    name = agents[0]['name']
    original_status = agents[0]['status']
    toggled = client.post(f'/api/agents/{name}/toggle').json()
    assert toggled['status'] != original_status

    servers = client.get('/api/servers').json()
    assert len(servers) > 0
