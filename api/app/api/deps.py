from fastapi import Depends, HTTPException, Request, status
from sqlmodel import Session, select

from app.core.database import get_session
from app.core.security import verify_access_token
from app.models.user import AppUser
from app.models.datasource import DataSource


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


def get_owned_datasource_or_404(
    session: Session,
    datasource_id: int,
    current_user: AppUser,
) -> DataSource:
    datasource = session.get(DataSource, datasource_id)
    if not datasource or datasource.user_id != current_user.user_id:
        raise HTTPException(status_code=404, detail="数据源不存在或无权限访问")
    return datasource
