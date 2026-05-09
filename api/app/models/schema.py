from typing import Optional
from sqlmodel import Field, SQLModel

class SchemaTableBase(SQLModel):
    datasource_id: int = Field(index=True, description="关联数据源ID")
    name: str = Field(description="表名")
    original_comment: Optional[str] = Field(default=None, description="数据库原始备注")
    supplementary_comment: Optional[str] = Field(default=None, description="人工补充/AI生成的备注")
    related_tables: Optional[str] = Field(default=None, description="关联表关系 (JSON串)")

class SchemaTable(SchemaTableBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True, description="自增ID")

class SchemaFieldBase(SQLModel):
    table_id: int = Field(index=True, description="关联表ID")
    name: str = Field(description="字段名")
    type: str = Field(description="数据类型")
    original_comment: Optional[str] = Field(default=None, description="数据库原始备注")
    supplementary_comment: Optional[str] = Field(default=None, description="人工补充/AI生成的备注")

class SchemaField(SchemaFieldBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True, description="自增ID")
