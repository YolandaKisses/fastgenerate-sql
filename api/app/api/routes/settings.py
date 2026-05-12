import os
import subprocess
from fastapi import APIRouter, Depends, HTTPException
import httpx
from sqlmodel import Session
from app.api.deps import get_current_user
from app.core.database import get_session
from app.models.setting import RuntimeSetting, RuntimeSettingUpdate
from app.services import setting_service
from app.core.config import settings as env_settings

router = APIRouter(prefix="/settings", tags=["settings"], dependencies=[Depends(get_current_user)])

@router.get("/")
def get_all_settings(session: Session = Depends(get_session)):
    # Return both db values and defaults
    return {
        "hermes_cli_path": {
            "value": setting_service.get_setting(session, "hermes_cli_path"),
            "default": env_settings.HERMES_CLI_PATH
        },
        "wiki_root": {
            "value": setting_service.get_setting(session, "wiki_root"),
            "default": env_settings.WIKI_ROOT
        },
        "rag_retrieval_backend": {
            "value": setting_service.get_setting(session, "rag_retrieval_backend"),
            "default": env_settings.RAG_RETRIEVAL_BACKEND
        },
        "lightrag_base_url": {
            "value": setting_service.get_setting(session, "lightrag_base_url"),
            "default": env_settings.LIGHTRAG_BASE_URL
        },
        "lightrag_api_key": {
            "value": setting_service.get_setting(session, "lightrag_api_key"),
            "default": env_settings.LIGHTRAG_API_KEY
        },
        "lightrag_timeout_seconds": {
            "value": setting_service.get_setting(session, "lightrag_timeout_seconds", str(env_settings.LIGHTRAG_TIMEOUT_SECONDS)),
            "default": str(env_settings.LIGHTRAG_TIMEOUT_SECONDS)
        },
        "lightrag_enable_remote_rebuild": {
            "value": setting_service.get_setting(session, "lightrag_enable_remote_rebuild", "true" if env_settings.LIGHTRAG_ENABLE_REMOTE_REBUILD else "false"),
            "default": "true" if env_settings.LIGHTRAG_ENABLE_REMOTE_REBUILD else "false"
        },
        "lightrag_enable_remote_ask": {
            "value": setting_service.get_setting(session, "lightrag_enable_remote_ask", "true" if env_settings.LIGHTRAG_ENABLE_REMOTE_ASK else "false"),
            "default": "true" if env_settings.LIGHTRAG_ENABLE_REMOTE_ASK else "false"
        }
    }

@router.post("/{key}")
def update_setting(key: str, req: RuntimeSettingUpdate, session: Session = Depends(get_session)):
    allowed_keys = [
        "hermes_cli_path",
        "wiki_root",
        "rag_retrieval_backend",
        "lightrag_base_url",
        "lightrag_api_key",
        "lightrag_timeout_seconds",
        "lightrag_enable_remote_rebuild",
        "lightrag_enable_remote_ask",
    ]
    if key not in allowed_keys:
        raise HTTPException(status_code=400, detail="不支持的配置键")
    return setting_service.set_setting(session, key, req.value)

@router.post("/test/hermes")
def test_hermes(session: Session = Depends(get_session)):
    cli_path = setting_service.get_setting(session, "hermes_cli_path", env_settings.HERMES_CLI_PATH)
    if not os.path.exists(cli_path):
        return {"status": "error", "message": f"可执行文件不存在: {cli_path}"}
    if not os.access(cli_path, os.X_OK):
        return {"status": "error", "message": f"文件没有执行权限: {cli_path}"}
    
    try:
        result = subprocess.run([cli_path, "--version"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return {"status": "success", "message": result.stdout.strip()}
        else:
            return {"status": "error", "message": f"执行报错: {result.stderr.strip()}"}
    except Exception as e:
        return {"status": "error", "message": f"执行异常: {str(e)}"}


@router.post("/test/lightrag")
def test_lightrag(session: Session = Depends(get_session)):
    base_url = setting_service.get_setting(session, "lightrag_base_url", env_settings.LIGHTRAG_BASE_URL) or ""
    timeout_raw = setting_service.get_setting(session, "lightrag_timeout_seconds", str(env_settings.LIGHTRAG_TIMEOUT_SECONDS)) or str(env_settings.LIGHTRAG_TIMEOUT_SECONDS)
    api_key = setting_service.get_setting(session, "lightrag_api_key", env_settings.LIGHTRAG_API_KEY) or ""
    if not base_url.strip():
        return {"status": "error", "message": "LightRAG 地址未配置"}

    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        timeout = float(timeout_raw)
        with httpx.Client(timeout=timeout) as client:
            response = client.get(base_url.rstrip("/") + env_settings.LIGHTRAG_HEALTH_PATH, headers=headers)
            response.raise_for_status()
        return {"status": "success", "message": f"LightRAG 可用: {base_url.rstrip('/')}{env_settings.LIGHTRAG_HEALTH_PATH}"}
    except Exception as exc:
        return {"status": "error", "message": f"LightRAG 连通性检查失败: {exc}"}
