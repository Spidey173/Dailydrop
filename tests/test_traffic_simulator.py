"""
Tests for TrafficSimulatorService: Autonomous order generation & daily activity heartbeat.
"""
import pytest
from app import create_app
from services.traffic_simulator_service import TrafficSimulatorService
from database import get_db_connection


@pytest.fixture
def test_app():
    app = create_app('testing')
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        yield app


@pytest.fixture
def admin_client():
    app = create_app('testing')
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['name'] = 'Admin User'
            sess['email'] = 'admin_dailydrop@gmail.com'
            sess['user_role'] = 'admin'
        yield client


@pytest.fixture
def unauth_client():
    app = create_app('testing')
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as client:
        yield client


def test_traffic_simulator_pulse(test_app):
    """Verify that pulse generates valid orders and order items in the database."""
    initial_orders = 0
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as cnt FROM orders")
            row = cur.fetchone()
            initial_orders = row['cnt'] if isinstance(row, dict) else row[0]

    created = TrafficSimulatorService.pulse(count=2)
    assert len(created) == 2
    for order in created:
        assert order['order_id'] > 0
        assert order['total_amount'] > 0
        assert order['city'] in ['Bangalore', 'Delhi NCR', 'Mumbai', 'Hyderabad', 'Pune']
        assert order['duration'] < 10.0
        assert order['items_count'] >= 1

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as cnt FROM orders")
            row = cur.fetchone()
            new_orders = row['cnt'] if isinstance(row, dict) else row[0]
            assert new_orders == initial_orders + 2


def test_ensure_daily_activity_runs_safely(test_app):
    """Verify ensure_daily_activity executes cleanly without error."""
    added = TrafficSimulatorService.ensure_daily_activity()
    assert isinstance(added, int)
    assert added >= 0


def test_api_traffic_pulse_unauth(unauth_client):
    """Verify unauthorized rejected for traffic pulse."""
    res_unauth = unauth_client.post('/api/v1/admin/traffic/pulse', json={'count': 1})
    assert res_unauth.status_code == 401


def test_api_traffic_pulse_admin(admin_client):
    """Verify admin allowed for traffic pulse."""
    res_admin = admin_client.post('/api/v1/admin/traffic/pulse', json={'count': 1})
    assert res_admin.status_code == 200
    data = res_admin.get_json()
    assert data['success'] is True
    assert 'orders' in data
    assert len(data['orders']) == 1


def test_api_traffic_catchup_unauth(unauth_client):
    """Verify unauthorized rejected for traffic catchup."""
    res_unauth = unauth_client.post('/api/v1/admin/traffic/catchup')
    assert res_unauth.status_code == 401


def test_api_traffic_catchup_admin(admin_client):
    """Verify admin allowed for traffic catchup."""
    res_admin = admin_client.post('/api/v1/admin/traffic/catchup')
    assert res_admin.status_code == 200
    data = res_admin.get_json()
    assert data['success'] is True
    assert 'orders_created' in data
