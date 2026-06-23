"""Environment configuration for the Massive MCP server."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    massive_api_key: str = ""
    massive_s3_access_key: str = ""
    massive_s3_secret_key: str = ""
    massive_api_base_url: str = "https://api.massive.com"
    massive_s3_endpoint: str = "https://files.massive.com"
    massive_s3_bucket: str = "flatfiles"
    mcp_port: int = 8082
    max_csv_rows: int = 5000
    flat_file_cache_dir: str = "/tmp/massive-flat-cache"
    flat_file_cache_ttl_hours: int = 24
    cloudflare_tunnel_token: str = ""
    public_mcp_hostname: str = ""

    def require_api_key(self) -> str:
        if not self.massive_api_key:
            raise ValueError("MASSIVE_API_KEY is not set")
        return self.massive_api_key

    def require_s3_credentials(self) -> tuple[str, str]:
        if not self.massive_s3_access_key or not self.massive_s3_secret_key:
            raise ValueError(
                "MASSIVE_S3_ACCESS_KEY and MASSIVE_S3_SECRET_KEY are required for flat files"
            )
        return self.massive_s3_access_key, self.massive_s3_secret_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
