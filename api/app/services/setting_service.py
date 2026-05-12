from sqlmodel import Session
from sqlmodel import select
from app.models.setting import RuntimeSetting
from app.core.config import settings

import os

def _coerce_setting_value(key: str, value: str):
    attr = key.upper()
    if not hasattr(settings, attr):
        return value
    current = getattr(settings, attr)
    if isinstance(current, bool):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(current, int):
        return int(value)
    if isinstance(current, float):
        return float(value)
    return value


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
    attr = key.upper()
    if hasattr(settings, attr):
        setattr(settings, attr, _coerce_setting_value(key, value))
    return db_setting


def hydrate_runtime_settings(session: Session) -> None:
    records = session.exec(select(RuntimeSetting)).all()
    for record in records:
        attr = record.key.upper()
        if hasattr(settings, attr):
            setattr(settings, attr, _coerce_setting_value(record.key, record.value))
