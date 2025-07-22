"""Configuration settings for ORAC STT service."""

import os
from pathlib import Path
from typing import Optional
from pydantic import BaseSettings, Field, validator


class ModelConfig(BaseSettings):
    """Model configuration settings."""
    
    name: str = Field(default="whisper-tiny-int8", env="MODEL_NAME")
    cache_dir: Path = Field(default=Path("/app/models"), env="MODEL_CACHE_DIR")
    device: str = Field(default="cuda", env="MODEL_DEVICE")
    
    @validator("cache_dir", pre=True)
    def validate_cache_dir(cls, v):
        if isinstance(v, str):
            return Path(v)
        return v

    class Config:
        env_prefix = "ORAC_MODEL_"


class APIConfig(BaseSettings):
    """API configuration settings."""
    
    host: str = Field(default="0.0.0.0", env="API_HOST")
    port: int = Field(default=8000, env="API_PORT")
    max_audio_duration: int = Field(default=15, env="MAX_AUDIO_DURATION")
    request_timeout: int = Field(default=20, env="REQUEST_TIMEOUT")
    
    class Config:
        env_prefix = "ORAC_API_"


class CommandAPIConfig(BaseSettings):
    """Command API client configuration."""
    
    url: str = Field(env="COMMAND_API_URL")
    timeout: int = Field(default=30, env="COMMAND_API_TIMEOUT")
    max_retries: int = Field(default=3, env="COMMAND_API_MAX_RETRIES")
    retry_delay: float = Field(default=1.0, env="COMMAND_API_RETRY_DELAY")
    
    class Config:
        env_prefix = "ORAC_"


class SecurityConfig(BaseSettings):
    """Security configuration settings."""
    
    enable_tls: bool = Field(default=False, env="ENABLE_TLS")
    cert_file: Optional[Path] = Field(default=None, env="CERT_FILE")
    key_file: Optional[Path] = Field(default=None, env="KEY_FILE")
    ca_file: Optional[Path] = Field(default=None, env="CA_FILE")
    enable_mtls: bool = Field(default=False, env="ENABLE_MTLS")
    
    @validator("cert_file", "key_file", "ca_file", pre=True)
    def validate_paths(cls, v):
        if v and isinstance(v, str):
            return Path(v)
        return v
    
    class Config:
        env_prefix = "ORAC_SECURITY_"


class Settings(BaseSettings):
    """Main application settings."""
    
    app_name: str = Field(default="ORAC STT Service", env="APP_NAME")
    environment: str = Field(default="production", env="ENVIRONMENT")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(default="json", env="LOG_FORMAT")
    
    model: ModelConfig = Field(default_factory=ModelConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    command_api: CommandAPIConfig = Field(default_factory=CommandAPIConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    
    class Config:
        env_prefix = "ORAC_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


def get_settings() -> Settings:
    """Get application settings instance."""
    return Settings()