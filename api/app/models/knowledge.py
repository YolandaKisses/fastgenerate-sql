from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class KnowledgeSyncTaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"


class KnowledgeSyncScope(str, Enum):
    DATASOURCE = "datasource"
    TABLE = "table"


class KnowledgeSyncMode(str, Enum):
    BASIC = "basic"
    AI_ENHANCED = "ai_enhanced"


class KnowledgeSyncTaskBase(SQLModel):
    datasource_id: int = Field(index=True)
    datasource_name: str
    status: KnowledgeSyncTaskStatus = Field(default=KnowledgeSyncTaskStatus.PENDING)
    scope: str = Field(default=KnowledgeSyncScope.DATASOURCE)
    mode: str = Field(default=KnowledgeSyncMode.BASIC)
    total_tables: int = 0
    completed_tables: int = 0
    failed_tables: int = 0
    output_root: str
    output_dir: str
    target_table_id: Optional[int] = None
    target_table_name: Optional[str] = None
    current_table: Optional[str] = None
    current_phase: Optional[str] = None
    last_message: Optional[str] = None
    error_message: Optional[str] = None


class KnowledgeSyncTask(KnowledgeSyncTaskBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    started_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)
