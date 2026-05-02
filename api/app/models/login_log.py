from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class LoginLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[str] = Field(default=None, index=True)
    account: str = Field(index=True)
    success: bool = Field(default=False)
    failure_reason: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
