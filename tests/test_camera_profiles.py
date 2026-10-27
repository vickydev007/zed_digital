import numpy as np
import pytest

from openset_reid.sensors.camera_profiles import (
    get_camera_profile,
    ProfileID,
    CAMERA_PROFILES,
    CameraSensorProfile,
)
from openset_reid.pipeline.video_analyzer import OfflineVideoAnalyzer


def test_default_cameras_resolve_default_profile():
    """Verify that cameras C1, C2, C3, C4 resolve strictly to PROFILE_DEFAULT_V1."""
    test_ids = [
        "c1", "camera_1", "cam-c2", "gate_turnstile_c3", "camera_c4_exit",
        "cam-entrance-south", None, ""
    ]
    for cid in test_ids:
        prof = get_camera_profile(cid)
        assert prof.profile_id == ProfileID.PROFILE_DEFAULT_V1.value
        assert prof.intensity_scale == 1.0
        assert prof.authorized_for_autonomous is True
        assert prof.requires_hardware_adjustment is False


def test_default_profile_preserves_images_bit_identically():
    """Verify that default profile causes zero modification or overhead to image arrays."""
    prof = get_camera_profile("cam_c2")
    sample_img = np.random.randint(0, 256, size=(128, 64, 3), dtype=np.uint8)
    processed = prof.apply_to_crop(sample_img)
    assert np.array_equal(sample_img, processed)


def test_camera_c5_resolves_photometric_profile():
    """Verify that camera C5 resolves to PROFILE_C5_PHOTOMETRIC_V1."""
    test_c5_ids = [
        "c5", "c5_overexposed", "cam_c5", "camera_c5_loading_dock", "camera-5"
    ]
    for cid in test_c5_ids:
        prof = get_camera_profile(cid)
        assert prof.profile_id == ProfileID.PROFILE_C5_PHOTOMETRIC_V1.value
        assert prof.intensity_scale == 0.8108
        assert prof.authorized_for_autonomous is False
        assert prof.requires_hardware_adjustment is True


def test_camera_c5_scales_intensity_correctly():
    """Verify that C5 profile scales pixel intensities by 0.8108x with proper clipping."""
    prof = get_camera_profile("c5")
    test_crop = np.full((10, 10, 3), 200, dtype=np.uint8)
    processed = prof.apply_to_crop(test_crop)

    expected_val = int(round(200 * 0.8108))
    assert np.all(processed == expected_val)


def test_cross_camera_contamination_prevented():
    """Prove that C5 profile cannot be applied to C2, C3, or C4 under any circumstances."""
    c2_prof = get_camera_profile("camera_c2")
    c3_prof = get_camera_profile("camera_c3")
    c4_prof = get_camera_profile("camera_c4")

    assert c2_prof.intensity_scale == 1.0
    assert c3_prof.intensity_scale == 1.0
    assert c4_prof.intensity_scale == 1.0

    assert c2_prof.profile_id != ProfileID.PROFILE_C5_PHOTOMETRIC_V1.value
    assert c3_prof.profile_id != ProfileID.PROFILE_C5_PHOTOMETRIC_V1.value
    assert c4_prof.profile_id != ProfileID.PROFILE_C5_PHOTOMETRIC_V1.value


def test_video_analyzer_integrates_camera_profile():
    """Verify OfflineVideoAnalyzer correctly inherits sensor profile for both normal and C5 cameras."""
    analyzer_c2 = OfflineVideoAnalyzer(
        onnx_model_path="experiments/deployment/openset_reid_v5.onnx",
        camera_id="cam_c2"
    )
    assert analyzer_c2.camera_profile.profile_id == ProfileID.PROFILE_DEFAULT_V1.value
    assert analyzer_c2.camera_profile.intensity_scale == 1.0

    analyzer_c5 = OfflineVideoAnalyzer(
        onnx_model_path="experiments/deployment/openset_reid_v5.onnx",
        camera_id="cam_c5"
    )
    assert analyzer_c5.camera_profile.profile_id == ProfileID.PROFILE_C5_PHOTOMETRIC_V1.value
    assert analyzer_c5.camera_profile.intensity_scale == 0.8108
    assert analyzer_c5.camera_profile.authorized_for_autonomous is False
