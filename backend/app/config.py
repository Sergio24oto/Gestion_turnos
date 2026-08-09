from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_database: str = "peluqueria"
    mysql_user: str = "root"
    mysql_password: str = ""
    admin_default_user: str = "admin"
    admin_default_password: str = "demo2026"
    secret_key: str = "change-this-secret-in-local-env"
    access_token_expire_minutes: int = 480
    frontend_origin: str = "http://localhost:5173"
    payment_reservation_minutes: int = 10
    mercadopago_access_token: str = ""
    mercadopago_webhook_secret: str = ""
    frontend_public_url: str = "http://localhost:5173"
    backend_public_url: str = "http://localhost:8000"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}?charset=utf8mb4"
        )


settings = Settings()
