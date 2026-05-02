from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import create_db_and_tables
from app.api.routes import auth, datasources, schema, workbench, audit, settings
from app.core.database import engine
from app.services.knowledge_service import mark_stale_knowledge_sync_tasks
from app.services.auth_service import ensure_default_admin_user
from app.services.datasource_service import encrypt_existing_datasource_passwords
from sqlmodel import Session

app = FastAPI(title="FastGenerate SQL API", version="1.0.0")

# 配置 CORS，方便前端 Vite 开发服务器直接调用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    create_db_and_tables()
    with Session(engine) as session:
        ensure_default_admin_user(session)
        encrypt_existing_datasource_passwords(session)
        mark_stale_knowledge_sync_tasks(session)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(datasources.router, prefix="/api/v1")
app.include_router(schema.router, prefix="/api/v1")
app.include_router(workbench.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")
app.include_router(settings.router, prefix="/api/v1")

@app.get("/api/v1/health")
def health_check():
    return {"status": "ok"}
