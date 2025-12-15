from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    # App
    APP_NAME: str = "Job Scout AI"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    
    # Database
    DATABASE_URL: str = "mysql+pymysql://root:password@localhost:3306/job_scout_ai"
    
    # OpenAI (optional - only needed for cover letter generation)
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-5.1"
    
    # Vector Store
    VECTOR_STORE_TYPE: str = "chroma"  # chroma or faiss
    CHROMA_DB_PATH: str = "./data/vector_store"
    
    # Storage
    RESUMES_DIR: str = "./data/resumes"
    COVER_LETTERS_DIR: str = "./data/cover_letters"
    LOGS_DIR: str = "./data/logs"
    
    # Redis cache (optional)
    REDIS_URL: Optional[str] = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Scheduler
    SCHEDULER_TIMEZONE: str = "UTC"
    CRAWL_SCHEDULE_HOUR: int = 6
    CRAWL_SCHEDULE_MINUTE: int = 0

    # Data retention / archiving
    JOB_RETENTION_DAYS: int = 30
    ARCHIVE_SCHEDULE_HOUR: int = 6
    ARCHIVE_SCHEDULE_MINUTE: int = 30

    # Daily export
    EXPORTS_DIR: str = "./data/exports"
    EXPORT_SCHEDULE_HOUR: int = 6
    EXPORT_SCHEDULE_MINUTE: int = 40
    
    # JWT
    JWT_SECRET_KEY: str = "your-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    
    # Crawler
    CRAWLER_TIMEOUT: int = 30
    CRAWLER_MAX_RETRIES: int = 3
    CRAWLER_USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    
    # LLM
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 1500
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
