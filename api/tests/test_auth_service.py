from datetime import datetime, timedelta

import pytest
from sqlmodel import SQLModel, Session, create_engine, select

from app.models.login_log import LoginLog
from app.models.user import AppUser
from app.services.auth_service import (
    authenticate_user,
    ensure_default_admin_user,
    record_login_log,
)
from app.core.security import (
    create_access_token,
    decrypt_password,
    encrypt_password_for_test,
    hash_password,
    verify_access_token,
    verify_password,
)


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_default_admin_user_is_created_with_hashed_password(session):
    user = ensure_default_admin_user(session)

    assert user.user_id
    assert user.name == "系统管理员"
    assert user.account == "admin"
    assert user.role == "admin"
    assert user.password_hash != "888888"
    assert verify_password("888888", user.password_salt, user.password_hash)


def test_existing_admin_password_is_not_reset_on_startup(session):
    user = ensure_default_admin_user(session)
    password_hash, password_salt = hash_password("changed-password")
    user.password_hash = password_hash
    user.password_salt = password_salt
    session.add(user)
    session.commit()

    existing = ensure_default_admin_user(session)

    assert verify_password("changed-password", existing.password_salt, existing.password_hash)
    assert not verify_password("888888", existing.password_salt, existing.password_hash)


def test_password_hash_uses_unique_salt():
    first_hash, first_salt = hash_password("888888")
    second_hash, second_salt = hash_password("888888")

    assert first_salt != second_salt
    assert first_hash != second_hash
    assert verify_password("888888", first_salt, first_hash)
    assert not verify_password("wrong", first_salt, first_hash)


def test_rsa_password_round_trip_for_login_payload():
    encrypted = encrypt_password_for_test("888888")

    assert encrypted != "888888"
    assert decrypt_password(encrypted) == "888888"


def test_authenticate_user_accepts_default_admin_and_rejects_wrong_password(session):
    ensure_default_admin_user(session)

    user = authenticate_user(session, "admin", "888888")

    assert user is not None
    assert user.account == "admin"
    assert authenticate_user(session, "admin", "bad-password") is None
    assert authenticate_user(session, "missing", "888888") is None


def test_access_token_round_trip_and_expiration(session):
    user = ensure_default_admin_user(session)
    token = create_access_token(user, expires_delta=timedelta(minutes=5))

    payload = verify_access_token(token)

    assert payload["sub"] == user.user_id
    assert payload["account"] == "admin"
    assert payload["role"] == "admin"

    expired = create_access_token(user, expires_delta=timedelta(minutes=-1))
    with pytest.raises(ValueError, match="Token 已过期"):
        verify_access_token(expired)


def test_login_log_records_success_and_failure(session):
    user = ensure_default_admin_user(session)

    record_login_log(session, account="admin", user=user, success=True, ip_address="127.0.0.1", user_agent="test")
    record_login_log(session, account="admin", user=None, success=False, failure_reason="密码错误")

    logs = session.exec(select(LoginLog).order_by(LoginLog.id)).all()

    assert len(logs) == 2
    assert logs[0].success is True
    assert logs[0].user_id == user.user_id
    assert logs[0].ip_address == "127.0.0.1"
    assert logs[1].success is False
    assert logs[1].failure_reason == "密码错误"
