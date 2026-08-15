from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str = "EDITH Agent"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    
    DATA_DIR: str = Field(
        default="~/edith_data",
        validation_alias="DATA_DIR"
    )
    
    SECRET_KEY: str = Field(
        default="dev-secret-change-in-production",
        validation_alias="SECRET_KEY"
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    NVIDIA_API_KEY: Optional[str] = Field(default=None, validation_alias="NVIDIA_API_KEY")
    NVIDIA_BASE_URL: str = Field(
        default="https://integrate.api.nvidia.com/v1",
        validation_alias="NVIDIA_BASE_URL"
    )
    
    OPENAI_API_KEY: Optional[str] = Field(default=None, validation_alias="OPENAI_API_KEY")
    
    TWILIO_ACCOUNT_SID: Optional[str] = Field(default=None, validation_alias="TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN: Optional[str] = Field(default=None, validation_alias="TWILIO_AUTH_TOKEN")
    TWILIO_PHONE_NUMBER: Optional[str] = Field(default=None, validation_alias="TWILIO_PHONE_NUMBER")
    
    STRIPE_SECRET_KEY: Optional[str] = Field(default=None, validation_alias="STRIPE_SECRET_KEY")
    STRIPE_WEBHOOK_SECRET: Optional[str] = Field(default=None, validation_alias="STRIPE_WEBHOOK_SECRET")
    
    BITWARDEN_CLIENT_ID: Optional[str] = Field(default=None, validation_alias="BITWARDEN_CLIENT_ID")
    BITWARDEN_CLIENT_SECRET: Optional[str] = Field(default=None, validation_alias="BITWARDEN_CLIENT_SECRET")
    
    DEFAULT_MODEL: str = "meta/llama-3.1-70b-instruct"
    FAST_MODEL: str = "meta/llama-3.1-8b-instruct"
    MAX_TOKENS: int = 8192
    TEMPERATURE: float = 0.7
    
    SPEND_LIMIT_PER_TXN: float = 500.0
    SPEND_LIMIT_PER_DAY: float = 2000.0
    
    VOICE_STT_MODEL: str = "whisper-1"
    VOICE_TTS_MODEL: str = "tts-1"
    VOICE_TTS_VOICE: str = "alloy"
    
    BROWSER_HEADLESS: bool = True
    BROWSER_TIMEOUT: int = 30000
    
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()