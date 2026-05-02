from datetime import datetime

from sqlmodel import Session, select

from app.core.security import hash_password, verify_password
from app.models.login_log import LoginLog
from app.models.user import AppUser

DEFAULT_ADMIN_ACCOUNT = "admin"
DEFAULT_ADMIN_PASSWORD = "888888"
DEFAULT_ADMIN_NAME = "系统管理员"


def ensure_default_admin_user(session: Session) -> AppUser:
    existing = session.exec(select(AppUser).where(AppUser.account == DEFAULT_ADMIN_ACCOUNT)).first()
    if existing:
        return existing

    password_hash, password_salt = hash_password(DEFAULT_ADMIN_PASSWORD)
    user = AppUser(
        name=DEFAULT_ADMIN_NAME,
        account=DEFAULT_ADMIN_ACCOUNT,
        password_hash=password_hash,
        password_salt=password_salt,
        role="admin",
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def authenticate_user(session: Session, account: str, password: str) -> AppUser | None:
    user = session.exec(select(AppUser).where(AppUser.account == account)).first()
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_salt, user.password_hash):
        return None
    user.last_login_at = datetime.now()
    user.updated_at = datetime.now()
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def record_login_log(
    session: Session,
    account: str,
    user: AppUser | None,
    success: bool,
    failure_reason: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> LoginLog:
    log = LoginLog(
        user_id=user.user_id if user else None,
        account=account,
        success=success,
        failure_reason=failure_reason,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    session.add(log)
    session.commit()
    session.refresh(log)
    return log
