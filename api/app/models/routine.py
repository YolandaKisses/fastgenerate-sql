from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class RoutineDefinitionBase(SQLModel):
    datasource_id: int = Field(index=True)
    owner: str
    name: str
    routine_type: str
    definition_text: str


class RoutineDefinition(RoutineDefinitionBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
