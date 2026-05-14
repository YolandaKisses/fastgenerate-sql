from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class SqlImportBatchStatus(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PARSED = "parsed"
    FAILED = "failed"


class SqlImportBatchBase(SQLModel):
    datasource_id: int = Field(index=True, description="关联数据源ID")
    batch_no: int = Field(description="同一数据源下的批次号")
    status: SqlImportBatchStatus = Field(default=SqlImportBatchStatus.UPLOADED, description="批次状态")
    message: Optional[str] = Field(default=None, description="批次说明/错误")


class SqlImportBatch(SqlImportBatchBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True, description="自增ID")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")


class SqlImportFileBase(SQLModel):
    batch_id: int = Field(index=True, description="关联批次ID")
    file_name: str = Field(description="原始文件名")
    file_content: str = Field(description="SQL 文本内容")
    sort_order: int = Field(default=0, description="上传顺序")


class SqlImportFile(SqlImportFileBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True, description="自增ID")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
