import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "FastGenerate SQL API"
    # 默认本地 SQLite 数据目录，Tauri 环境下可被覆写
    DATA_DIR: str = os.path.expanduser("~/.fastgenerate_sql_data")
    OBSIDIAN_VAULT_ROOT: str = os.path.expanduser("~/Documents/obsidian知识库/FastGenerate SQL")
    HERMES_CLI_PATH: str = os.path.expanduser("~/.local/bin/hermes")
    AUTH_TOKEN_SECRET: str = ""
    AUTH_TOKEN_EXPIRE_MINUTES: int = 480
    
    @property
    def DATABASE_URL(self) -> str:
        os.makedirs(self.DATA_DIR, exist_ok=True)
        db_path = os.path.join(self.DATA_DIR, "fastgenerate.db")
        return f"sqlite:///{db_path}"

settings = Settings()
