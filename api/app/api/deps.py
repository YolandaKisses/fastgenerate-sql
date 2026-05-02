from fastapi import Depends, HTTPException, Request, status
from sqlmodel import Session, select

from app.core.database import get_session
from app.core.security import verify_access_token
from app.models.user import AppUser


def get_current_user(request: Request, session: Session = Depends(get_session)) -> AppUser:
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录或登录已过期")

    try:
        payload = verify_access_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    user = session.exec(select(AppUser).where(AppUser.user_id == payload.get("sub"))).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="用户已禁用")
    return user
