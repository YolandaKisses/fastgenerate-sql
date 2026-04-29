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

class DataSourceBase(SQLModel):
    name: str = Field(index=True)
    db_type: str  # mysql, postgresql, oracle
    host: str
    port: int
    database: str
    username: str
    status: DataSourceStatus = Field(default=DataSourceStatus.DRAFT)

class DataSource(DataSourceBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    password: str # 实际应加密存储
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

class DataSourceCreate(DataSourceBase):
    password: str

class DataSourceRead(DataSourceBase):
    id: int
    created_at: datetime
    updated_at: datetime

class DataSourceUpdate(SQLModel):
    name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    status: Optional[DataSourceStatus] = None
