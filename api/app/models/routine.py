from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class RoutineDefinitionBase(SQLModel):
    datasource_id: int = Field(index=True, description="数据源ID")
    owner: str = Field(description="所有者/Schema")
    name: str = Field(description="对象名称")
    routine_type: str = Field(description="对象类型 (PROCEDURE/FUNCTION)")
    definition_text: str = Field(description="定义代码原文")
    lineage_status: str = Field(default="pending", description="SQL 血缘解析状态")
    lineage_message: Optional[str] = Field(default=None, description="SQL 血缘解析备注")


class RoutineDefinition(RoutineDefinitionBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True, description="自增ID")
    created_at: datetime = Field(default_factory=datetime.now, description="记录创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="最后同步时间")
    lineage_updated_at: Optional[datetime] = Field(default=None, description="血缘解析更新时间")


class RoutineSqlFactBase(SQLModel):
    datasource_id: int = Field(index=True, description="数据源ID")
    routine_id: int = Field(index=True, description="存储过程ID")
    statement_index: int = Field(description="SQL 语句顺序")
    statement_text: str = Field(description="抽取出的 SQL 原文")
    table_name: str = Field(index=True, description="命中的表名")
    normalized_table_name: str = Field(index=True, description="标准化表名")
    usage_type: str = Field(description="表使用方式 (read/write)")
    parser_name: str = Field(default="sqllineage", description="解析器名称")
    is_dynamic: bool = Field(default=False, description="是否来自动态 SQL")


class RoutineSqlFact(RoutineSqlFactBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True, description="自增ID")
    created_at: datetime = Field(default_factory=datetime.now, description="记录创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="最后更新时间")
