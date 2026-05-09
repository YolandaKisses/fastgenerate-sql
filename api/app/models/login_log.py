from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class LoginLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True, description="自增ID")
    user_id: Optional[str] = Field(default=None, index=True, description="关联用户ID")
    account: str = Field(index=True, description="登录账号")
    success: bool = Field(default=False, description="是否登录成功")
    failure_reason: Optional[str] = Field(default=None, description="失败原因")
    ip_address: Optional[str] = Field(default=None, description="IP地址")
    user_agent: Optional[str] = Field(default=None, description="浏览器User-Agent")
    created_at: datetime = Field(default_factory=datetime.now, description="记录时间")
