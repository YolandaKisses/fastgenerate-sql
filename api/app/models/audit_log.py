from typing import Optional
from datetime import datetime
from sqlmodel import Field, SQLModel

class AuditLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    datasource_id: int = Field(index=True)
    datasource_name: str  # 快照，删除数据源后仍可读
    question: str
    clarified: bool = False
    clarification_content: Optional[str] = None
    sql: Optional[str] = None
    executed: bool = False
    execution_status: Optional[str] = None  # success / empty / error
    duration_ms: Optional[int] = None
    error_summary: Optional[str] = None
    row_count: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.now)
