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
    CANCELLED = "cancelled"


class KnowledgeSyncScope(str, Enum):
    DATASOURCE = "datasource"
    TABLE = "table"


class KnowledgeSyncMode(str, Enum):
    BASIC = "basic"
    AI_ENHANCED = "ai_enhanced"


class KnowledgeSyncTaskBase(SQLModel):
    datasource_id: int = Field(index=True, description="关联数据源ID")
    datasource_name: str = Field(description="关联数据源名称")
    status: KnowledgeSyncTaskStatus = Field(default=KnowledgeSyncTaskStatus.PENDING, description="任务状态")
    scope: str = Field(default=KnowledgeSyncScope.DATASOURCE, description="同步范围 (datasource/table)")
    mode: str = Field(default=KnowledgeSyncMode.BASIC, description="同步模式 (basic/ai_enhanced)")
    total_tables: int = Field(default=0, description="需要同步的总表数")
    completed_tables: int = Field(default=0, description="已完成同步的表数")
    failed_tables: int = Field(default=0, description="同步失败的表数")
    is_incremental: bool = Field(default=False, description="是否为增量同步（跳过已存在页面）")
    output_root: str = Field(description="知识库输出根目录")
    output_dir: str = Field(description="知识库输出子目录")
    target_table_id: Optional[int] = Field(default=None, description="单表同步时的目标表ID")
    target_table_name: Optional[str] = Field(default=None, description="单表同步时的目标表名")
    current_table: Optional[str] = Field(default=None, description="当前正在处理的表名")
    current_phase: Optional[str] = Field(default=None, description="当前处理阶段")
    last_message: Optional[str] = Field(default=None, description="最后一条运行日志")
    failed_table_names: Optional[str] = Field(default=None, description="同步失败的表名列表 (JSON)")
    error_message: Optional[str] = Field(default=None, description="错误详情")


class KnowledgeSyncTask(KnowledgeSyncTaskBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True, description="自增ID")
    started_at: Optional[datetime] = Field(default=None, description="任务开始时间")
    updated_at: Optional[datetime] = Field(default=None, description="任务最后更新时间")
    finished_at: Optional[datetime] = Field(default=None, description="任务完成时间")
    created_at: datetime = Field(default_factory=datetime.now, description="记录创建时间")
