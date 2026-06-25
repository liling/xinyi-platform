from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="XINYI_PLATFORM_",
        env_file=".env",
        extra="ignore",
    )

    database_url: str
    manager_schema: str = "xinyi"

    jwt_secret: str
    encryption_key: str

    admin_username: str = "admin"
    admin_password: str = ""

    auth_provider: str = "local"

    cas_server_url: str = ""
    cas_service_url: str = ""

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    session_expire_hours: int = 24
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_days: int = 7
    oauth_code_ttl_seconds: int = 60

    host: str = "0.0.0.0"
    port: int = 8000
    base_url: str = "http://localhost:8000"
    brand_name: str = "平台"
    manager_url: str = "http://localhost:8001"

    rate_limit_login_per_minute: int = 5
    rate_limit_register_per_minute: int = 3

    session_secure: bool = False

    registration_token: str = ""


def get_settings() -> Settings:
    return Settings()
