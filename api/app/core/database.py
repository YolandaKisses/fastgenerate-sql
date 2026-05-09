from sqlmodel import SQLModel, create_engine, Session
import sqlalchemy
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL, 
    echo=settings.DB_ECHO, 
    connect_args={"check_same_thread": False, "timeout": 30}
)

import app.models.setting  # 确保 RuntimeSetting 被注册到 SQLModel.metadata
import app.models.user  # 确保 AppUser 被注册到 SQLModel.metadata
import app.models.login_log  # 确保 LoginLog 被注册到 SQLModel.metadata
import app.models.routine  # 确保存储过程定义表被注册到 SQLModel.metadata
def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
    ensure_compatible_schema()


def _is_sqlite_readonly_error(exc: sqlalchemy.exc.OperationalError) -> bool:
    message = str(exc).lower()
    return "readonly database" in message or "read-only database" in message


def ensure_compatible_schema():
    try:
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
            if "scope" not in sync_task_column_names:
                conn.execute(sqlalchemy.text("ALTER TABLE knowledgesynctask ADD COLUMN scope VARCHAR DEFAULT 'datasource'"))
            if "mode" not in sync_task_column_names:
                conn.execute(sqlalchemy.text("ALTER TABLE knowledgesynctask ADD COLUMN mode VARCHAR DEFAULT 'basic'"))
            if "target_table_id" not in sync_task_column_names:
                conn.execute(sqlalchemy.text("ALTER TABLE knowledgesynctask ADD COLUMN target_table_id INTEGER"))
            if "target_table_name" not in sync_task_column_names:
                conn.execute(sqlalchemy.text("ALTER TABLE knowledgesynctask ADD COLUMN target_table_name VARCHAR"))
            if "updated_at" not in sync_task_column_names:
                conn.execute(sqlalchemy.text("ALTER TABLE knowledgesynctask ADD COLUMN updated_at DATETIME"))

            ds_columns = conn.execute(sqlalchemy.text("PRAGMA table_info(datasource)")).fetchall()
            ds_column_names = {row[1] for row in ds_columns}
            if "auth_type" not in ds_column_names:
                conn.execute(sqlalchemy.text("ALTER TABLE datasource ADD COLUMN auth_type VARCHAR DEFAULT 'password'"))

            # SchemaTable 迁移
            table_columns = conn.execute(sqlalchemy.text("PRAGMA table_info(schematable)")).fetchall()
            table_column_names = {row[1] for row in table_columns}
            if "related_tables" not in table_column_names:
                conn.execute(sqlalchemy.text("ALTER TABLE schematable ADD COLUMN related_tables VARCHAR"))
    except sqlalchemy.exc.OperationalError as exc:
        if _is_sqlite_readonly_error(exc):
            return
        raise

def get_session():
    with Session(engine) as session:
        yield session
