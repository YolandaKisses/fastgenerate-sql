from sqlmodel import Session
from app.models.setting import RuntimeSetting
from app.core.config import settings

import os

def get_setting(session: Session, key: str, default: str | None = None) -> str | None:
    """获取运行时设置，如果数据库中没有，回退到环境变量或默认值"""
    value = None
    db_setting = session.get(RuntimeSetting, key)
    if db_setting:
        value = db_setting.value
    elif hasattr(settings, key.upper()):
        value = getattr(settings, key.upper())
    else:
        value = default
        
    if isinstance(value, str) and value.startswith("~"):
        value = os.path.expanduser(value)
        
    return value

def set_setting(session: Session, key: str, value: str, description: str | None = None):
    """保存或更新运行时设置"""
    db_setting = session.get(RuntimeSetting, key)
    if db_setting:
        db_setting.value = value
        if description:
            db_setting.description = description
    else:
        db_setting = RuntimeSetting(key=key, value=value, description=description)
    
    session.add(db_setting)
    session.commit()
    return db_setting
