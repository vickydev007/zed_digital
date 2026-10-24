from __future__ import annotations
import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = 'Open-Set ReID Enterprise Platform'
    API_V1_PREFIX: str = '/api/v1'
    DATABASE_URL: str = os.getenv('DATABASE_URL', 'sqlite:///./data/reid_system.db')
    SECRET_KEY: str = os.getenv('SECRET_KEY', '7e9c5a1f2b4c6e8d0a3b5c7e9f1a3c5e7b9d1f3a5c7e9b1d3f5a7c9e1b3d5f7a')
    ENCRYPTION_KEY: str = os.getenv('ENCRYPTION_KEY', 'w8H6PqZ0Jm2K9X4Lb7N5F3R1v8T6Y0U2I4O6P8A0S2D=')
    JWT_ALGORITHM: str = 'HS256'
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    UPLOAD_DIR: str = os.getenv('UPLOAD_DIR', 'data/uploads')
    CROPS_DIR: str = os.getenv('CROPS_DIR', 'data/crops')
    OUTPUT_VIDEOS_DIR: str = os.getenv('OUTPUT_VIDEOS_DIR', 'data/outputs')
    ONNX_MODEL_PATH: str = os.getenv('ONNX_MODEL_PATH', 'experiments/deployment/openset_reid.onnx')
    PYTORCH_MODEL_PATH: str = os.getenv('PYTORCH_MODEL_PATH', 'experiments/best_model.pth')
    DEFAULT_SCORE_THRESHOLD: float = 0.7124
    DEFAULT_CONTRAST_MARGIN: float = 0.05
    DEFAULT_QUALITY_MIN_H: int = 28
    DEFAULT_QUALITY_MIN_W: int = 12
    DEFAULT_QUALITY_MIN_BLUR: float = 30.0

    model_config = SettingsConfigDict(env_file='.env', case_sensitive=True)

settings = Settings()
