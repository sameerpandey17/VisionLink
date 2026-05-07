from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    redis_url: str = "redis://redis:6379"
    max_frame_size_bytes: int = 10 * 1024 * 1024  # 10 MB
    cors_origins: str = "http://localhost:3000,http://localhost"

    # Security — set API_KEY in .env to enable authentication.
    # If left empty, the /ingest endpoint is open (dev/local mode).
    # WHY: Documented in audit — unauthenticated /ingest allows anyone to
    #      flood the system with frames, filling disk and crashing workers.
    api_key: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def auth_enabled(self) -> bool:
        return bool(self.api_key)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()  # type: ignore[call-arg]
