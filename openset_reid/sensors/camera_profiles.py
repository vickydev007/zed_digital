from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Any
import numpy as np
import cv2


class ProfileID(str, Enum):
    PROFILE_DEFAULT_V1 = "PROFILE-DEFAULT-V1"
    PROFILE_C5_PHOTOMETRIC_V1 = "PROFILE-C5-PHOTOMETRIC-V1"


@dataclass(frozen=True)
class CameraSensorProfile:
    profile_id: str
    camera_match_tag: str
    description: str
    intensity_scale: float
    authorized_for_autonomous: bool
    requires_hardware_adjustment: bool

    def apply_to_crop(self, crop_bgr: np.ndarray) -> np.ndarray:
        """Apply sensor profile correction to cropped person bounding box."""
        if self.intensity_scale == 1.0 or crop_bgr is None or crop_bgr.size == 0:
            return crop_bgr
        scaled = np.clip(crop_bgr.astype(np.float32) * self.intensity_scale, 0.0, 255.0)
        return scaled.astype(np.uint8)


CAMERA_PROFILES: Dict[str, CameraSensorProfile] = {
    ProfileID.PROFILE_DEFAULT_V1.value: CameraSensorProfile(
        profile_id=ProfileID.PROFILE_DEFAULT_V1.value,
        camera_match_tag="default",
        description="Standard calibrated sensor profile for cameras C1, C2, C3, C4. Zero software scaling.",
        intensity_scale=1.0,
        authorized_for_autonomous=True,
        requires_hardware_adjustment=False,
    ),
    ProfileID.PROFILE_C5_PHOTOMETRIC_V1.value: CameraSensorProfile(
        profile_id=ProfileID.PROFILE_C5_PHOTOMETRIC_V1.value,
        camera_match_tag="c5",
        description=(
            "Camera C5 photometric intensity scaling (0.8108x) compensating for over-exposure. "
            "Strictly GATED from autonomous operations pending hardware shutter/gain calibration."
        ),
        intensity_scale=0.8108,
        authorized_for_autonomous=False,
        requires_hardware_adjustment=True,
    ),
}


def get_camera_profile(camera_identifier: Optional[str] = None) -> CameraSensorProfile:
    """
    Resolve camera profile based on camera ID or name.
    Strictly guarantees that only C5 can receive PROFILE_C5_PHOTOMETRIC_V1.
    All other cameras receive PROFILE_DEFAULT_V1.
    """
    if not camera_identifier:
        return CAMERA_PROFILES[ProfileID.PROFILE_DEFAULT_V1.value]

    cid_clean = camera_identifier.strip().lower()

    is_c5 = (
        cid_clean == "c5"
        or cid_clean.startswith("c5_")
        or cid_clean.startswith("cam_c5")
        or cid_clean.startswith("camera_c5")
        or cid_clean.startswith("camera-5")
        or "_c5_" in cid_clean
        or cid_clean.endswith("_c5")
    )

    if is_c5:
        return CAMERA_PROFILES[ProfileID.PROFILE_C5_PHOTOMETRIC_V1.value]

    return CAMERA_PROFILES[ProfileID.PROFILE_DEFAULT_V1.value]
