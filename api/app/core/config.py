import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "FastGenerate SQL API"
    # 默认本地 SQLite 数据目录，Tauri 环境下可被覆写
    DATA_DIR: str = os.path.expanduser("~/.fastgenerate_sql_data")
    WIKI_ROOT: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../wiki"))
    HERMES_CLI_PATH: str = os.path.expanduser("~/.local/bin/hermes")
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_LLM_MODEL: str = "deepseek-v4-flash"
    AUTH_TOKEN_SECRET: str = ""
    AUTH_TOKEN_EXPIRE_MINUTES: int = 480
    ALLOWED_ORIGINS: str = "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:4173,http://localhost:4173"
    DB_ECHO: bool = False

    @property
    def cors_allowed_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.ALLOWED_ORIGINS.split(",")
            if origin.strip() and origin.strip() != "*"
        ]
    
    @property
    def DATABASE_URL(self) -> str:
        os.makedirs(self.DATA_DIR, exist_ok=True)
        db_path = os.path.join(self.DATA_DIR, "fastgenerate.db")
        return f"sqlite:///{db_path}"

settings = Settings()
