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


class KnowledgeSyncTaskBase(SQLModel):
    datasource_id: int = Field(index=True)
    datasource_name: str
    status: KnowledgeSyncTaskStatus = Field(default=KnowledgeSyncTaskStatus.PENDING)
    total_tables: int = 0
    completed_tables: int = 0
    failed_tables: int = 0
    output_root: str
    output_dir: str
    error_message: Optional[str] = None


class KnowledgeSyncTask(KnowledgeSyncTaskBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)
