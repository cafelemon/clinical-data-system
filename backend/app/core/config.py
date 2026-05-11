from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    app_name: str = "临床数据收集系统"
    app_env: str = "development"
    app_debug: bool = True
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api"

    database_url: str = "postgresql+psycopg://clinical_user:clinical_pass@localhost:5432/clinical_data"

    jwt_secret_key: str = "change-this-secret-key"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    initial_admin_username: str = "admin"
    initial_admin_password: str = "Admin@123456"
    initial_admin_full_name: str = "系统管理员"
    initial_admin_email: str | None = None

    file_storage_root: Path = PROJECT_ROOT / "data-dev" / "file-storage"
    max_upload_size_mb: int = 200
    pdf_packet_ocr_api_url: str | None = "http://127.0.0.1:8048"
    pdf_packet_ocr_dpi: int = 120
    pdf_packet_ocr_timeout_seconds: int = 600
    pdf_packet_ocr_command: str | None = None
    backend_cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
