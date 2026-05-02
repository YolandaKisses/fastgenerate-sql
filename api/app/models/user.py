from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlmodel import Field, SQLModel


class AppUser(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(default_factory=lambda: uuid4().hex, unique=True, index=True)
    name: str
    account: str = Field(unique=True, index=True)
    password_hash: str
    password_salt: str
    role: str = Field(default="admin")
    is_active: bool = Field(default=True)
    last_login_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class UserRead(SQLModel):
    user_id: str
    name: str
    account: str
    role: str
