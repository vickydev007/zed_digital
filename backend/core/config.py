from __future__ import annotations
import os
from typing import Any, Optional
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
    ONNX_MODEL_PATH: str = os.getenv('ONNX_MODEL_PATH', 'experiments/deployment/openset_reid_v5.onnx')
    PYTORCH_MODEL_PATH: str = os.getenv('PYTORCH_MODEL_PATH', 'experiments/best_model.pth')
    ACTIVE_POLICY_ID: str = os.getenv('ACTIVE_POLICY_ID', 'POL-ALERTING-V1')
    DEFAULT_SCORE_THRESHOLD: float = float(os.getenv('DEFAULT_SCORE_THRESHOLD', '0.85'))
    DEFAULT_CONTRAST_MARGIN: float = float(os.getenv('DEFAULT_CONTRAST_MARGIN', '0.10'))
    DEFAULT_MIN_OBSERVATIONS: int = int(os.getenv('DEFAULT_MIN_OBSERVATIONS', '3'))
    FRAME_SCORE_THRESHOLD: float = float(os.getenv('FRAME_SCORE_THRESHOLD', '0.70'))
    FRAME_CONTRAST_MARGIN: float = float(os.getenv('FRAME_CONTRAST_MARGIN', '0.04'))
    DEFAULT_QUALITY_MIN_H: int = 28
    DEFAULT_QUALITY_MIN_W: int = 12
    DEFAULT_QUALITY_MIN_BLUR: float = 30.0
    ALLOWED_CAMERA_SUBNETS: str = os.getenv('ALLOWED_CAMERA_SUBNETS', '')
    CAMERA_INFERENCE_DEVICE: str = os.getenv('CAMERA_INFERENCE_DEVICE', 'auto')
    CAMERA_CONNECT_TIMEOUT_SECONDS: float = float(os.getenv('CAMERA_CONNECT_TIMEOUT_SECONDS', '10.0'))
    CAMERA_RECONNECT_MAX_BACKOFF: float = float(os.getenv('CAMERA_RECONNECT_MAX_BACKOFF', '30.0'))
    CAMERA_INFERENCE_SAMPLE_RATE: int = int(os.getenv('CAMERA_INFERENCE_SAMPLE_RATE', '2'))

    @classmethod
    def _validate_threshold(cls, v: float, name: str) -> float:
        if not (0.0 < v <= 1.0):
            raise ValueError(f"{name} must be within (0.0, 1.0], got {v}")
        return float(v)

    @classmethod
    def _validate_margin(cls, v: float, name: str) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"{name} must be within [0.0, 1.0], got {v}")
        return float(v)

    def __post_init__(self):
        pass

    def model_post_init(self, __context: Any) -> None:
        if self.ACTIVE_POLICY_ID not in ('POL-SUPERVISED-V1', 'POL-ALERTING-V1', 'POL-AUTONOMOUS-V1'):
            raise ValueError(f"Unknown ACTIVE_POLICY_ID: '{self.ACTIVE_POLICY_ID}'.")
        if self.ACTIVE_POLICY_ID == 'POL-AUTONOMOUS-V1':
            raise ValueError(
                "POL-AUTONOMOUS-V1 is RESTRICTED_BLOCKED from production deployment. "
                "Autonomous access control is blocked until high-assurance hardware and statistical gates "
                "(one-sided 95% FAR < 1.0% over N>=299 independent trials) are met."
            )
        self._validate_threshold(self.DEFAULT_SCORE_THRESHOLD, "DEFAULT_SCORE_THRESHOLD")
        self._validate_margin(self.DEFAULT_CONTRAST_MARGIN, "DEFAULT_CONTRAST_MARGIN")
        if self.DEFAULT_MIN_OBSERVATIONS < 1:
            raise ValueError(f"DEFAULT_MIN_OBSERVATIONS must be >= 1, got {self.DEFAULT_MIN_OBSERVATIONS}")
        self._validate_threshold(self.FRAME_SCORE_THRESHOLD, "FRAME_SCORE_THRESHOLD")
        self._validate_margin(self.FRAME_CONTRAST_MARGIN, "FRAME_CONTRAST_MARGIN")
        if self.DEFAULT_QUALITY_MIN_H < 10 or self.DEFAULT_QUALITY_MIN_W < 10:
            raise ValueError("Minimum quality box dimensions must be >= 10 pixels")
        if self.DEFAULT_QUALITY_MIN_BLUR < 5.0:
            raise ValueError("Minimum blur variance threshold must be >= 5.0")

    @property
    def effective_allow_private_rtsp(self) -> bool:
        """
        Unified policy rule:
        Private network RTSP access requires BOTH ALLOW_PRIVATE_RTSP and ALLOW_PRIVATE_RTSP_NETWORKS
        to be truthy. If an invalid or unparseable value is configured, fails safely to False.
        """
        def _parse_bool(val: Any) -> Optional[bool]:
            if isinstance(val, bool):
                return val
            if not isinstance(val, str):
                return None
            s = val.strip().lower()
            if s in ('true', '1', 'yes', 'on'):
                return True
            if s in ('false', '0', 'no', 'off'):
                return False
            return None

        val1 = _parse_bool(os.getenv('ALLOW_PRIVATE_RTSP', 'true'))
        val2 = _parse_bool(os.getenv('ALLOW_PRIVATE_RTSP_NETWORKS', 'true'))
        if val1 is None or val2 is None:
            return False
        return bool(val1 and val2)

    ALLOW_PRIVATE_RTSP_NETWORKS: bool = True
    ALLOW_PRIVATE_RTSP: bool = True

    def __init__(self, **values: Any):
        super().__init__(**values)
        eff = self.effective_allow_private_rtsp
        self.ALLOW_PRIVATE_RTSP = eff
        self.ALLOW_PRIVATE_RTSP_NETWORKS = eff

    model_config = SettingsConfigDict(env_file='.env', case_sensitive=True)

settings = Settings()
