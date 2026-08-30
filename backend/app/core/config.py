import os
from pydantic import Field
from pydantic_settings import BaseSettings

class LimitsConfig(BaseSettings):
    ID_MAX_LENGTH: int = 50
    EMAIL_MAX_LENGTH: int = 255
    PHONE_MAX_LENGTH: int = 50
    CURRENCY_MAX_LENGTH: int = 3
    REFERENCE_MAX_LENGTH: int = 100
    DESCRIPTION_MAX_LENGTH: int = 1000
    WEBHOOK_MAX_BYTES: int = 5242880  # 5 MB
    
    class Config:
        env_prefix = "LIMITS_"

class PaginationConfig(BaseSettings):
    DEFAULT_PAGE_SIZE: int = 50
    MAX_PAGE_SIZE: int = 100
    
    class Config:
        env_prefix = "PAGINATION_"

class SecurityConfig(BaseSettings):
    JWT_SECRET_KEY: str = Field(..., description="Strictly required JWT Secret Key. App fails if missing.")
    JWT_EXPIRY_MINUTES: int = 30
    ALGORITHM: str = "HS256"
    
    class Config:
        env_file = ".env"
        extra = "ignore"

class RazorpayConfig(BaseSettings):
    KEY_ID: str = Field(..., description="Razorpay Key ID")
    KEY_SECRET: str = Field(..., description="Razorpay Key Secret")
    WEBHOOK_SECRET: str = Field(..., description="Razorpay Webhook Secret")
    API_BASE_URL: str = "https://api.razorpay.com/v1"
    TIMEOUT_CONNECT: int = 5
    TIMEOUT_READ: int = 15
    TIMEOUT_WRITE: int = 5
    MAX_RETRIES: int = 3
    
    class Config:
        env_prefix = "RAZORPAY_"
        env_file = ".env"
        extra = "ignore"

class AppSettings(BaseSettings):
    # IMMUTABLE TECHNICAL INVARIANT: None
    
    # PRODUCTION CONFIGURATION
    TESTING: str = "0"
    DATABASE_URL: str = Field(..., description="PostgreSQL DB URL")
    
    # SAFE DEVELOPMENT DEFAULT (Can be overridden in production)
    WORKER_POLL_INTERVAL: int = 5
    ML_ENABLED: bool = True
    
    # BUSINESS POLICY boundaries are defined in policy.json, not here.
    
    limits: LimitsConfig = LimitsConfig()
    pagination: PaginationConfig = PaginationConfig()
    
    @property
    def security(self) -> SecurityConfig:
        return SecurityConfig()
        
    @property
    def razorpay(self) -> RazorpayConfig:
        return RazorpayConfig()

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = AppSettings()
