from sqlmodel import SQLModel, create_engine, Session
import sqlalchemy
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL, 
    echo=True, 
    connect_args={"check_same_thread": False}
)

import app.models.setting  # 确保 RuntimeSetting 被注册到 SQLModel.metadata
def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
    ensure_compatible_schema()


def ensure_compatible_schema():
    with engine.begin() as conn:
        columns = conn.execute(sqlalchemy.text("PRAGMA table_info(auditlog)")).fetchall()
        column_names = {row[1] for row in columns}
        if "used_notes" not in column_names:
            conn.execute(sqlalchemy.text("ALTER TABLE auditlog ADD COLUMN used_notes VARCHAR"))

        sync_task_columns = conn.execute(sqlalchemy.text("PRAGMA table_info(knowledgesynctask)")).fetchall()
        sync_task_column_names = {row[1] for row in sync_task_columns}
        if "failed_tables" not in sync_task_column_names:
            conn.execute(sqlalchemy.text("ALTER TABLE knowledgesynctask ADD COLUMN failed_tables INTEGER DEFAULT 0"))

def get_session():
    with Session(engine) as session:
        yield session
