"""
Bill Analyzer App - Configuration
Production-level configuration management
"""
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # App
    APP_NAME: str = "Bill Analyzer API"
    DEBUG: bool = False
    VERSION: str = "1.0.0"
    
    # Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    TEMP_DIR: Path = BASE_DIR / "temp"
    
    # File Upload
    MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50MB
    ALLOWED_EXTENSIONS: set = {".pdf", ".png", ".jpg", ".jpeg"}
    
    # OCR
    TESSERACT_CMD: str = r"C:\Program Files\Tesseract-OCR\tesseract.exe"  # Windows path
    OCR_DPI: int = 300
    OCR_LANG: str = "eng"
    
    # Forgery Detection Thresholds
    FONT_MISMATCH_THRESHOLD: float = 0.8
    OCR_MISMATCH_THRESHOLD: float = 0.85
    METADATA_SUSPICIOUS_KEYWORDS: list = [
        "photoshop", "gimp", "illustrator", "inkscape",
        "edited", "modified", "foxit", "pdfescape"
    ]
    
    # Processing
    MAX_WORKERS: int = 4
    TIMEOUT_SECONDS: int = 120
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()

# Ensure directories exist
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.TEMP_DIR.mkdir(parents=True, exist_ok=True)
