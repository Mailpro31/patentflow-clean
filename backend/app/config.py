from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import List, Union


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Environment
    ENVIRONMENT: str = "dev"
    
    # Application
    APP_NAME: str = "PatentFlowIA"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    
    # Database
    DATABASE_URL: str
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
    
    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    
    # Embedding Configuration
    EMBEDDING_PROVIDER: str = "sentence_transformers"  # "vertex_ai" or "sentence_transformers"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"  # SentenceTransformer model
    EMBEDDING_DIMENSION: int = 384  # Dimension of embeddings
    
    # Vertex AI Configuration (optional)
    VERTEX_AI_PROJECT_ID: str = ""
    VERTEX_AI_LOCATION: str = "us-central1"
    VERTEX_AI_MODEL: str = "textembedding-gecko@003"
    GOOGLE_APPLICATION_CREDENTIALS: str = ""  # Path to service account JSON
    
    # Espacenet Configuration
    ESPACENET_API_URL: str = "https://ops.epo.org/3.2/rest-services"
    BRIGHT_DATA_PROXY: str = ""  # Optional proxy configuration
    REDIS_CACHE_TTL: int = 604800  # 7 days in seconds
    
    # Gemini AI Configuration
    GEMINI_MODEL: str = "gemini-1.5-pro-latest"
    GEMINI_API_KEY: str = ""
    GEMINI_TEMPERATURE_LARGE: float = 0.3
    GEMINI_TEMPERATURE_TECHNIQUE: float = 0.5
    GEMINI_TEMPERATURE_INPI: float = 0.2
    GEMINI_MAX_TOKENS: int = 8192
    
    # Text Linting
    ENABLE_TEXT_LINTER: bool = True
    AUTO_REMOVE_ADJECTIVES: bool = True
    QUALITY_SCORE_THRESHOLD: int = 70
    
    # Stable Diffusion Configuration
    SD_API_PROVIDER: str = "replicate"  # "replicate" or "stability_ai"
    REPLICATE_API_KEY: str = ""
    STABILITY_AI_API_KEY: str = ""
    SD_MODEL: str = "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b"
    CONTROLNET_LINE_ART_SCALE: float = 0.8
    SD_NUM_INFERENCE_STEPS: int = 30
    SD_GUIDANCE_SCALE: float = 7.5
    
    # SAM2 Configuration
    SAM2_MODEL: str = "facebook/sam2-hiera-large"
    SAM2_DEVICE: str = "cpu"  # or "cuda" if GPU available
    SAM2_POINTS_PER_SIDE: int = 32
    SAM2_MIN_MASK_AREA: int = 100
    
    # Vectorization
    POTRACE_TURNPOLICY: str = "minority"
    POTRACE_TURDSIZE: int = 2
    POTRACE_ALPHAMAX: float = 1.0
    SVG_OPTIMIZE: bool = True
    
    # Annotation
    AUTO_LABEL_START_NUMBER: int = 10
    AUTO_LABEL_INCREMENT: int = 10
    LABEL_FONT_SIZE: int = 14
    ADD_LEADER_LINES: bool = True
    
    # Stripe Configuration
    STRIPE_API_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_TAX_ENABLED: bool = True
    
    # Woleet Blockchain
    WOLEET_API_KEY: str = ""
    WOLEET_API_URL: str = "https://api.woleet.io/v1"
    
    # INPI Annuities
    INPI_DISCOUNT_RATE: float = 0.02
    INPI_REMINDER_MONTHS: int = 6
    
    # Embedding (legacy - keep for backward compatibility)
    EMBEDDING_API_URL: str = "http://localhost:8001"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )


# Global settings instance
settings = Settings()
