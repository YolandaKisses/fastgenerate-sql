import os
import subprocess
from fastapi import APIRouter, Depends, HTTPException
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
        }
    }

@router.post("/{key}")
def update_setting(key: str, req: RuntimeSettingUpdate, session: Session = Depends(get_session)):
    allowed_keys = ["hermes_cli_path", "wiki_root"]
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


