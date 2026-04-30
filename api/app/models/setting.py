from datetime import datetime
from sqlmodel import Field, SQLModel
from typing import Optional

class RuntimeSetting(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str
    description: Optional[str] = None
    updated_at: datetime = Field(default_factory=datetime.now)

class RuntimeSettingUpdate(SQLModel):
    value: str
