from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class RoutineDefinitionBase(SQLModel):
    datasource_id: int = Field(index=True, description="数据源ID")
    owner: str = Field(description="所有者/Schema")
    name: str = Field(description="对象名称")
    routine_type: str = Field(description="对象类型 (PROCEDURE/FUNCTION)")
    definition_text: str = Field(description="定义代码原文")


class RoutineDefinition(RoutineDefinitionBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True, description="自增ID")
    created_at: datetime = Field(default_factory=datetime.now, description="记录创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="最后同步时间")
