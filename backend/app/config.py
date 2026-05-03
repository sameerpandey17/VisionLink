from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    max_frame_size_bytes: int = 10 * 1024 * 1024  # 10 MB
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()  # type: ignore[call-arg]
