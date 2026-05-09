from typing import Optional
from datetime import datetime
from sqlmodel import Field, SQLModel
from enum import Enum

class DataSourceStatus(str, Enum):
    DRAFT = "draft"
    CONNECTION_FAILED = "connection_failed"
    CONNECTION_OK = "connection_ok"
    SYNC_FAILED = "sync_failed"
    STALE = "stale"


class SyncStatus(str, Enum):
    NEVER_SYNCED = "never_synced"
    SYNCING = "syncing"
    SYNC_SUCCESS = "sync_success"
    SYNC_FAILED = "sync_failed"
    SYNC_PARTIAL_SUCCESS = "sync_partial_success"

class DataSourceBase(SQLModel):
    name: str = Field(index=True, description="数据源名称")
    db_type: str = Field(description="数据库类型 (mysql, postgresql, oracle)")
    host: str = Field(description="主机地址")
    port: int = Field(description="端口号")
    database: str = Field(description="数据库名/服务名")
    username: str = Field(description="用户名")
    auth_type: str = Field(default="password", description="认证类型 (password, wallet 等)")
    status: DataSourceStatus = Field(default=DataSourceStatus.DRAFT, description="连接状态")
    sync_status: SyncStatus = Field(default=SyncStatus.NEVER_SYNCED, description="知识库同步状态")
    last_sync_message: Optional[str] = Field(default=None, description="最后一次同步的消息/错误")
    user_id: Optional[str] = Field(default=None, index=True, description="所属用户ID")

class DataSource(DataSourceBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True, description="自增ID")
    user_id: str = Field(index=True, description="所属用户ID")  # Override to make it required in DB
    password: str = Field(description="密码 (加密存储)")
    last_synced_at: Optional[datetime] = Field(default=None, description="上一次成功同步的时间")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")

class DataSourceCreate(DataSourceBase):
    password: str

class DataSourceRead(DataSourceBase):
    id: int
    user_id: str
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
    auth_type: Optional[str] = None
    status: Optional[DataSourceStatus] = None
