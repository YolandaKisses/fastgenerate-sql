from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_session
from app.core.security import create_access_token, decrypt_password, get_public_key_pem
from app.models.user import AppUser, UserRead
from app.services.auth_service import authenticate_user, record_login_log

router = APIRouter(prefix="/auth", tags=["auth"])

# Simple memory-based rate limiting
_FAILED_ATTEMPTS = {}  # key: (ip_address, account), value: (fail_count, lock_until)
MAX_FAILURES = 5
LOCKOUT_DURATION = timedelta(minutes=15)

def _check_rate_limit(ip_address: str, account: str):
    key = (ip_address, account)
    now = datetime.now()
    if key in _FAILED_ATTEMPTS:
        fail_count, lock_until = _FAILED_ATTEMPTS[key]
        if lock_until and now < lock_until:
            return False, lock_until
        elif lock_until and now >= lock_until:
            _FAILED_ATTEMPTS[key] = (0, None)
    return True, None

def _record_failure(ip_address: str, account: str):
    key = (ip_address, account)
    now = datetime.now()
    fail_count, _ = _FAILED_ATTEMPTS.get(key, (0, None))
    fail_count += 1
    lock_until = None
    if fail_count >= MAX_FAILURES:
        lock_until = now + LOCKOUT_DURATION
    _FAILED_ATTEMPTS[key] = (fail_count, lock_until)

def _clear_failures(ip_address: str, account: str):
    key = (ip_address, account)
    if key in _FAILED_ATTEMPTS:
        del _FAILED_ATTEMPTS[key]


class LoginRequest(BaseModel):
    account: str
    password: str


class LoginResponse(BaseModel):
    token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserRead


@router.get("/public-key")
def read_public_key():
    return {
        "algorithm": "RSA-OAEP",
        "hash": "SHA-256",
        "public_key": get_public_key_pem(),
    }


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, request: Request, session: Session = Depends(get_session)):
    account = req.account.strip()
    ip_address = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent")

    allowed, lock_until = _check_rate_limit(ip_address, account)
    if not allowed:
        record_login_log(session, account=account, user=None, success=False, failure_reason="连续失败次数过多，临时锁定", ip_address=ip_address, user_agent=user_agent)
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"连续失败次数过多，账户已被锁定至 {lock_until.strftime('%H:%M:%S')}")

    if not account or not req.password:
        _record_failure(ip_address, account)
        record_login_log(session, account=account, user=None, success=False, failure_reason="请求格式错误", ip_address=ip_address, user_agent=user_agent)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请输入账号和密码")

    try:
        password = decrypt_password(req.password)
    except Exception as exc:
        _record_failure(ip_address, account)
        record_login_log(session, account=account, user=None, success=False, failure_reason="密码解密失败", ip_address=ip_address, user_agent=user_agent)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="密码格式无效") from exc

    existing_user = session.exec(select(AppUser).where(AppUser.account == account)).first()
    if existing_user and not existing_user.is_active:
        _record_failure(ip_address, account)
        record_login_log(session, account=account, user=existing_user, success=False, failure_reason="用户已禁用", ip_address=ip_address, user_agent=user_agent)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="用户已禁用")

    user = authenticate_user(session, account, password)
    if not user:
        _record_failure(ip_address, account)
        record_login_log(session, account=account, user=existing_user, success=False, failure_reason="账号或密码错误", ip_address=ip_address, user_agent=user_agent)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号或密码错误")

    _clear_failures(ip_address, account)
    record_login_log(session, account=account, user=user, success=True, ip_address=ip_address, user_agent=user_agent)
    token = create_access_token(user)
    return {
        "token": token,
        "token_type": "bearer",
        "expires_in": settings.AUTH_TOKEN_EXPIRE_MINUTES * 60,
        "user": UserRead(user_id=user.user_id, name=user.name, account=user.account, role=user.role),
    }


@router.get("/me", response_model=UserRead)
def read_me(current_user: AppUser = Depends(get_current_user)):
    return UserRead(
        user_id=current_user.user_id,
        name=current_user.name,
        account=current_user.account,
        role=current_user.role,
    )
