from sqlmodel import SQLModel, create_engine, Session
import sqlalchemy
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL, 
    echo=True, 
    connect_args={"check_same_thread": False}
)

import app.models.setting  # 确保 RuntimeSetting 被注册到 SQLModel.metadata
import app.models.user  # 确保 AppUser 被注册到 SQLModel.metadata
import app.models.login_log  # 确保 LoginLog 被注册到 SQLModel.metadata
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
        if "current_table" not in sync_task_column_names:
            conn.execute(sqlalchemy.text("ALTER TABLE knowledgesynctask ADD COLUMN current_table VARCHAR"))
        if "current_phase" not in sync_task_column_names:
            conn.execute(sqlalchemy.text("ALTER TABLE knowledgesynctask ADD COLUMN current_phase VARCHAR"))
        if "last_message" not in sync_task_column_names:
            conn.execute(sqlalchemy.text("ALTER TABLE knowledgesynctask ADD COLUMN last_message VARCHAR"))

        ds_columns = conn.execute(sqlalchemy.text("PRAGMA table_info(datasource)")).fetchall()
        ds_column_names = {row[1] for row in ds_columns}
        if "auth_type" not in ds_column_names:
            conn.execute(sqlalchemy.text("ALTER TABLE datasource ADD COLUMN auth_type VARCHAR DEFAULT 'password'"))

def get_session():
    with Session(engine) as session:
        yield session
