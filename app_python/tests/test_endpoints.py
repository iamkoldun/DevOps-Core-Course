import pytest
from app import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


def test_index_returns_200(client):
    r = client.get('/')
    assert r.status_code == 200
    assert r.content_type == 'application/json'


def test_index_json_structure(client):
    r = client.get('/')
    data = r.get_json()
    assert 'service' in data
    assert 'system' in data
    assert 'runtime' in data
    assert 'request' in data
    assert 'endpoints' in data


def test_index_service_fields(client):
    r = client.get('/')
    data = r.get_json()
    svc = data['service']
    assert svc['name'] == 'devops-info-service'
    assert svc['version'] == '1.0.0'
    assert 'description' in svc
    assert svc['framework'] == 'Flask'


def test_index_system_fields(client):
    r = client.get('/')
    data = r.get_json()
    sys_info = data['system']
    assert 'hostname' in sys_info
    assert 'platform' in sys_info
    assert 'platform_version' in sys_info
    assert 'architecture' in sys_info
    assert 'cpu_count' in sys_info
    assert isinstance(sys_info['cpu_count'], int)
    assert 'python_version' in sys_info


def test_index_runtime_fields(client):
    r = client.get('/')
    data = r.get_json()
    rt = data['runtime']
    assert 'uptime_seconds' in rt
    assert isinstance(rt['uptime_seconds'], int)
    assert 'uptime_human' in rt
    assert 'current_time' in rt
    assert rt.get('timezone') == 'UTC'


def test_index_request_fields(client):
    r = client.get('/')
    data = r.get_json()
    req = data['request']
    assert 'client_ip' in req
    assert 'user_agent' in req
    assert req['method'] == 'GET'
    assert req['path'] == '/'


def test_index_endpoints_list(client):
    r = client.get('/')
    data = r.get_json()
    endpoints = data['endpoints']
    assert isinstance(endpoints, list)
    paths = [e['path'] for e in endpoints]
    assert '/' in paths
    assert '/health' in paths


def test_health_returns_200(client):
    r = client.get('/health')
    assert r.status_code == 200
    assert r.content_type == 'application/json'


def test_health_json_structure(client):
    r = client.get('/health')
    data = r.get_json()
    assert data['status'] == 'healthy'
    assert 'timestamp' in data
    assert 'uptime_seconds' in data
    assert isinstance(data['uptime_seconds'], int)


def test_health_uptime_non_negative(client):
    r = client.get('/health')
    data = r.get_json()
    assert data['uptime_seconds'] >= 0


def test_404_for_unknown_path(client):
    r = client.get('/nonexistent')
    assert r.status_code == 404
    data = r.get_json()
    assert 'error' in data
    assert data.get('error') == 'Not Found'


def test_index_method_not_allowed(client):
    r = client.post('/')
    assert r.status_code == 405
