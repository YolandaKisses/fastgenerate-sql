from typing import Optional
from sqlmodel import Field, SQLModel

class SchemaTableBase(SQLModel):
    datasource_id: int = Field(index=True)
    name: str
    original_comment: Optional[str] = None
    supplementary_comment: Optional[str] = None
    related_tables: Optional[str] = None

class SchemaTable(SchemaTableBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

class SchemaFieldBase(SQLModel):
    table_id: int = Field(index=True)
    name: str
    type: str
    original_comment: Optional[str] = None
    supplementary_comment: Optional[str] = None

class SchemaField(SchemaFieldBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
