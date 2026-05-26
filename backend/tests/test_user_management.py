"""用户与企业空间权限管理测试。"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.authentication import hash_password
from app.core.enterprise_space_context import is_bootstrap_admin
from app.core.initialization import initialize_admin_and_default_space
from app.core.membership_roles import MEMBER, SPACE_ADMIN
from app.core.user_permissions import (
    assert_can_set_is_admin,
    can_manage_user,
    ensure_not_last_space_admin,
    validate_role,
)
from app.db.base import Base
from app.main import app
from app.models.enterprise_space import EnterpriseSpace, Membership, User
from app.db.session import get_db


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session: Session) -> TestClient:
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _login(client: TestClient, username: str, password: str) -> str:
    resp = client.post("/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_validate_role_rejects_unknown():
    with pytest.raises(Exception):
        validate_role("owner")


def test_ensure_not_last_space_admin_blocks(db_session: Session):
    user = User(username="sa", email="sa@test.com", password_hash="x", is_active=True)
    space = EnterpriseSpace(name="s1", slug="s1")
    db_session.add_all([user, space])
    db_session.flush()
    membership = Membership(user_id=user.id, enterprise_space_id=space.id, role=SPACE_ADMIN)
    db_session.add(membership)
    db_session.commit()

    with pytest.raises(Exception):
        ensure_not_last_space_admin(db_session, space.id, membership)


def test_bootstrap_admin_flag(db_session: Session):
    initialize_admin_and_default_space(db_session)
    admin = db_session.execute(select(User).where(User.username == "admin")).scalar_one()
    assert is_bootstrap_admin(admin) is True


def test_system_admin_lists_all_users(client: TestClient, db_session: Session):
    initialize_admin_and_default_space(db_session)
    token = _login(client, "admin", "ChangeMe123!")
    headers = {"Authorization": f"Bearer {token}", "X-Enterprise-Space": "default"}

    resp = client.post(
        "/users",
        json={"username": "u1", "email": "u1@test.com", "password": "password1"},
        headers=headers,
    )
    assert resp.status_code == 201

    resp = client.get("/users", headers=headers)
    assert resp.status_code == 200
    usernames = {u["username"] for u in resp.json()}
    assert "u1" in usernames
    assert "admin" in usernames


def test_space_admin_creates_user_in_current_space(client: TestClient, db_session: Session):
    initialize_admin_and_default_space(db_session)
    admin_token = _login(client, "admin", "ChangeMe123!")
    admin_headers = {"Authorization": f"Bearer {admin_token}", "X-Enterprise-Space": "default"}

    client.post(
        "/enterprise-spaces",
        json={"name": "Acme", "slug": "acme", "description": "test"},
        headers=admin_headers,
    )
    client.post(
        "/users",
        json={
            "username": "spaceadmin",
            "email": "spaceadmin@test.com",
            "password": "password1",
            "space_assignments": [{"enterprise_space_id": 2, "role": SPACE_ADMIN}],
        },
        headers=admin_headers,
    )

    sa_token = _login(client, "spaceadmin", "password1")
    sa_headers = {"Authorization": f"Bearer {sa_token}", "X-Enterprise-Space": "acme"}

    resp = client.post(
        "/users",
        json={"username": "member1", "email": "member1@test.com", "password": "password1"},
        headers=sa_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["memberships"]) == 1
    assert data["memberships"][0]["space"]["slug"] == "acme"
    assert data["memberships"][0]["role"] == MEMBER


def test_non_bootstrap_admin_cannot_set_is_admin(client: TestClient, db_session: Session):
    initialize_admin_and_default_space(db_session)
    admin_token = _login(client, "admin", "ChangeMe123!")
    headers = {"Authorization": f"Bearer {admin_token}", "X-Enterprise-Space": "default"}

    client.post(
        "/users",
        json={
            "username": "sysadmin2",
            "email": "sysadmin2@test.com",
            "password": "password1",
            "is_admin": True,
        },
        headers=headers,
    )

    sys_token = _login(client, "sysadmin2", "password1")
    sys_headers = {"Authorization": f"Bearer {sys_token}", "X-Enterprise-Space": "default"}

    resp = client.patch(
        "/users/1",
        json={"is_admin": False},
        headers=sys_headers,
    )
    assert resp.status_code == 403


def test_user_without_space_gets_403_on_knowledge_base(client: TestClient, db_session: Session):
    initialize_admin_and_default_space(db_session)
    admin_token = _login(client, "admin", "ChangeMe123!")
    admin_headers = {"Authorization": f"Bearer {admin_token}", "X-Enterprise-Space": "default"}

    client.post(
        "/users",
        json={"username": "lonely", "email": "lonely@test.com", "password": "password1"},
        headers=admin_headers,
    )

    lonely_token = _login(client, "lonely", "password1")
    lonely_headers = {"Authorization": f"Bearer {lonely_token}", "X-Enterprise-Space": "default"}

    resp = client.get("/knowledge-bases", headers=lonely_headers)
    assert resp.status_code == 403


def test_create_user_without_email(client: TestClient, db_session: Session):
    initialize_admin_and_default_space(db_session)
    token = _login(client, "admin", "ChangeMe123!")
    headers = {"Authorization": f"Bearer {token}", "X-Enterprise-Space": "default"}

    resp = client.post(
        "/users",
        json={"username": "noemail", "password": "password1"},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["email"] is None


def test_multi_space_assignment(client: TestClient, db_session: Session):
    initialize_admin_and_default_space(db_session)
    token = _login(client, "admin", "ChangeMe123!")
    headers = {"Authorization": f"Bearer {token}", "X-Enterprise-Space": "default"}

    client.post(
        "/enterprise-spaces",
        json={"name": "Beta", "slug": "beta", "description": ""},
        headers=headers,
    )
    create_resp = client.post(
        "/users",
        json={"username": "multi", "email": "multi@test.com", "password": "password1"},
        headers=headers,
    )
    user_id = create_resp.json()["id"]

    resp = client.put(
        f"/users/{user_id}/memberships",
        json={
            "assignments": [
                {"enterprise_space_id": 1, "role": MEMBER},
                {"enterprise_space_id": 2, "role": MEMBER},
            ]
        },
        headers=headers,
    )
    assert resp.status_code == 200
    assert len(resp.json()["memberships"]) == 2

    spaces_resp = client.get("/enterprise-spaces", headers={"Authorization": f"Bearer {_login(client, 'multi', 'password1')}"})
    assert len(spaces_resp.json()) == 2
