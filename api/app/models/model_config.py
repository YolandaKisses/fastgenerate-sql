from typing import Optional
from datetime import datetime
from sqlmodel import Field, SQLModel

class ModelConfigBase(SQLModel):
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model_name: str = "gpt-4o"
    timeout: int = 30
    temperature: float = 0.0

class ModelConfig(ModelConfigBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
