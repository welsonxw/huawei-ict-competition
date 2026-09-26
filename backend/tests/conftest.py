import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def login(client, role="expert", username=None):
    from app.services.auth import create_user

    username = username or role
    create_user(username, "password123", role)
    res = client.post("/api/auth/login", json={"username": username, "password": "password123"})
    assert res.status_code == 200
    return res.get_json()


@pytest.fixture
def expert(client):
    return login(client, "expert")
