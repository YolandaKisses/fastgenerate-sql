from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlmodel import Field, SQLModel


class AppUser(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True, description="自增ID")
    user_id: str = Field(default_factory=lambda: uuid4().hex, unique=True, index=True, description="用户唯一标识(UUID)")
    name: str = Field(description="用户姓名")
    account: str = Field(unique=True, index=True, description="登录账号")
    password_hash: str = Field(description="密码哈希值")
    password_salt: str = Field(description="密码盐值")
    role: str = Field(default="admin", description="用户角色")
    is_active: bool = Field(default=True, description="是否启用")
    last_login_at: Optional[datetime] = Field(default=None, description="最后登录时间")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")


class UserRead(SQLModel):
    user_id: str
    name: str
    account: str
    role: str
