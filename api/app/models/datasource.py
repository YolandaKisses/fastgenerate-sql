from typing import Optional
from datetime import datetime
from sqlmodel import Field, SQLModel
from enum import Enum

class DataSourceStatus(str, Enum):
    DRAFT = "draft"
    CONNECTION_FAILED = "connection_failed"
    CONNECTION_OK = "connection_ok"
    SYNC_FAILED = "sync_failed"
    READY = "ready"
    STALE = "stale"


class SyncStatus(str, Enum):
    NEVER_SYNCED = "never_synced"
    SYNCING = "syncing"
    SYNC_SUCCESS = "sync_success"
    SYNC_FAILED = "sync_failed"
    SYNC_PARTIAL_SUCCESS = "sync_partial_success"

class DataSourceBase(SQLModel):
    name: str = Field(index=True)
    db_type: str  # mysql, postgresql, oracle
    host: str
    port: int
    database: str
    username: str
    status: DataSourceStatus = Field(default=DataSourceStatus.DRAFT)
    sync_status: SyncStatus = Field(default=SyncStatus.NEVER_SYNCED)
    last_sync_message: Optional[str] = None

class DataSource(DataSourceBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    password: str # 实际应加密存储
    last_synced_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

class DataSourceCreate(DataSourceBase):
    password: str

class DataSourceRead(DataSourceBase):
    id: int
    last_synced_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

class DataSourceUpdate(SQLModel):
    name: Optional[str] = None
    db_type: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    status: Optional[DataSourceStatus] = None
