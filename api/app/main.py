from contextlib import asynccontextmanager
import os
import sys

# Oracle Thick Mode 初始化 (必须在任何数据库连接之前调用)
try:
    import oracledb
    # 优先从环境变量读取，如果没有则使用你刚安装的默认路径
    oracle_client_path = os.getenv("ORACLE_CLIENT_PATH", "/Users/yolanda/opt/oracle/instantclient_23_26")
    if oracle_client_path and os.path.exists(oracle_client_path):
        oracledb.init_oracle_client(lib_dir=oracle_client_path)
        print(f"✅ Oracle Thick Mode initialized using: {oracle_client_path}")
    else:
        print("ℹ️ Oracle running in Thin Mode (Default)")
except Exception as e:
    print(f"⚠️ Failed to initialize Oracle Thick Mode: {e}")


from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from app.core.config import settings as app_settings
from app.core.database import create_db_and_tables
from app.api.routes import auth, datasources, schema, settings
from app.core.database import engine
from app.services.knowledge_service import mark_stale_knowledge_sync_tasks
from app.services.auth_service import ensure_default_admin_user
from app.services.datasource_service import encrypt_existing_datasource_passwords
from sqlmodel import Session


def run_startup_tasks():
    create_db_and_tables()
    with Session(engine) as session:
        ensure_default_admin_user(session)
        encrypt_existing_datasource_passwords(session)
        mark_stale_knowledge_sync_tasks(session)


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_startup_tasks()
    yield


app = FastAPI(title="FastGenerate SQL API", version="1.0.0", lifespan=lifespan)

# 配置 CORS，方便前端 Vite 开发服务器直接调用
app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(datasources.router, prefix="/api/v1")
app.include_router(schema.router, prefix="/api/v1")
app.include_router(settings.router, prefix="/api/v1")

@app.get("/api/v1/health")
def health_check():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "error", "checks": {"database": "error"}},
        ) from exc

    return {"status": "ok", "checks": {"database": "ok"}}
