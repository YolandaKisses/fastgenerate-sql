from datetime import datetime
from sqlmodel import Field, SQLModel
from typing import Optional

class RuntimeSetting(SQLModel, table=True):
    key: str = Field(primary_key=True, description="配置键名")
    value: str = Field(description="配置值")
    description: Optional[str] = Field(default=None, description="配置描述")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")

class RuntimeSettingUpdate(SQLModel):
    value: str
