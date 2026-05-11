from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class ViewDefinitionBase(SQLModel):
    datasource_id: int = Field(index=True, description="数据源ID")
    owner: str = Field(description="所有者/Schema")
    name: str = Field(description="视图名称")
    definition_text: str = Field(description="视图定义原文")
    original_comment: Optional[str] = Field(default=None, description="数据库原始备注")
    lineage_status: str = Field(default="pending", description="SQL 血缘解析状态")
    lineage_message: Optional[str] = Field(default=None, description="SQL 血缘解析备注")


class ViewDefinition(ViewDefinitionBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True, description="自增ID")
    created_at: datetime = Field(default_factory=datetime.now, description="记录创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="最后同步时间")
    lineage_updated_at: Optional[datetime] = Field(default=None, description="血缘解析更新时间")


class ViewSqlFactBase(SQLModel):
    datasource_id: int = Field(index=True, description="数据源ID")
    view_id: int = Field(index=True, description="视图ID")
    statement_text: str = Field(description="视图定义原文")
    table_name: str = Field(index=True, description="命中的底层表名")
    normalized_table_name: str = Field(index=True, description="标准化表名")
    usage_type: str = Field(default="read", description="表使用方式 (read)")
    parser_name: str = Field(default="sqllineage", description="解析器名称")


class ViewSqlFact(ViewSqlFactBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True, description="自增ID")
    created_at: datetime = Field(default_factory=datetime.now, description="记录创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="最后更新时间")
