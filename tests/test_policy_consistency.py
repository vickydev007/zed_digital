import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.core.config import settings
from openset_reid.open_set.policies import (
    OPERATIONAL_POLICIES,
    PolicyID,
    get_policy,
    list_policies,
)


@pytest.fixture
def client():
    return TestClient(app)


def test_immutable_policy_definitions():
    """Verify all 3 immutable operational policies exist with expected parameters."""
    assert PolicyID.POL_SUPERVISED_V1.value in OPERATIONAL_POLICIES
    assert PolicyID.POL_ALERTING_V1.value in OPERATIONAL_POLICIES
    assert PolicyID.POL_AUTONOMOUS_V1.value in OPERATIONAL_POLICIES

    pol_a = get_policy(PolicyID.POL_SUPERVISED_V1.value)
    assert pol_a.tau == 0.70
    assert pol_a.delta == 0.04
    assert pol_a.min_obs == 1
    assert pol_a.status == "AUTHORIZED_SUPERVISED"
    assert pol_a.requires_human_verification is True

    pol_b = get_policy(PolicyID.POL_ALERTING_V1.value)
    assert pol_b.tau == 0.85
    assert pol_b.delta == 0.10
    assert pol_b.min_obs == 3
    assert pol_b.status == "AUTHORIZED_CONDITIONAL"
    assert pol_b.requires_human_verification is True

    pol_c = get_policy(PolicyID.POL_AUTONOMOUS_V1.value)
    assert pol_c.tau == 0.88
    assert pol_c.delta == 0.12
    assert pol_c.min_obs == 5
    assert pol_c.status == "RESTRICTED_BLOCKED"
    assert pol_c.requires_human_verification is False


def test_backend_config_matches_active_policy():
    """Verify backend settings strictly align with active policy POL-ALERTING-V1."""
    assert settings.ACTIVE_POLICY_ID == PolicyID.POL_ALERTING_V1.value
    active_policy = get_policy(settings.ACTIVE_POLICY_ID)

    assert settings.DEFAULT_SCORE_THRESHOLD == active_policy.tau
    assert settings.DEFAULT_CONTRAST_MARGIN == active_policy.delta
    assert settings.DEFAULT_MIN_OBSERVATIONS == active_policy.min_obs


def test_frame_level_config_matches_supervised_policy():
    """Verify frame-level candidate settings align with POL-SUPERVISED-V1."""
    supervised_policy = get_policy(PolicyID.POL_SUPERVISED_V1.value)
    assert settings.FRAME_SCORE_THRESHOLD == supervised_policy.tau
    assert settings.FRAME_CONTRAST_MARGIN == supervised_policy.delta


def test_api_health_endpoint_reports_active_policy(client):
    """Verify /health reports active policy and corresponding operational thresholds."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "healthy"
    assert data["active_policy_id"] == PolicyID.POL_ALERTING_V1.value
    assert data["operating_tau"] == 0.85
    assert data["operating_margin"] == 0.10
    assert data["operating_min_obs"] == 3


def test_api_policies_endpoint(client):
    """Verify /policies exposes all registered policies and active policy details."""
    resp = client.get("/policies")
    assert resp.status_code == 200
    data = resp.json()

    assert data["active_policy_id"] == PolicyID.POL_ALERTING_V1.value
    assert "active_policy" in data
    assert data["active_policy"]["tau"] == 0.85
    assert data["active_policy"]["delta"] == 0.10
    assert data["active_policy"]["min_obs"] == 3

    assert "all_policies" in data
    assert PolicyID.POL_SUPERVISED_V1.value in data["all_policies"]
    assert PolicyID.POL_ALERTING_V1.value in data["all_policies"]
    assert PolicyID.POL_AUTONOMOUS_V1.value in data["all_policies"]


def test_policy_lookup_invalid_key():
    """Verify requesting an invalid policy ID raises a clean ValueError."""
    with pytest.raises(ValueError, match="Unknown operational policy"):
        get_policy("INVALID-POLICY-XYZ")


def test_settings_blocks_autonomous_policy_at_startup():
    """Verify configuring POL-AUTONOMOUS-V1 as active policy is rejected with clean error."""
    from backend.core.config import Settings
    with pytest.raises(ValueError, match="RESTRICTED_BLOCKED"):
        Settings(ACTIVE_POLICY_ID="POL-AUTONOMOUS-V1")


def test_settings_validates_threshold_ranges():
    """Verify Settings rejects out-of-range thresholds and observation counts."""
    from backend.core.config import Settings
    with pytest.raises(ValueError, match="DEFAULT_SCORE_THRESHOLD"):
        Settings(DEFAULT_SCORE_THRESHOLD=1.5)

    with pytest.raises(ValueError, match="DEFAULT_CONTRAST_MARGIN"):
        Settings(DEFAULT_CONTRAST_MARGIN=-0.05)

    with pytest.raises(ValueError, match="DEFAULT_MIN_OBSERVATIONS"):
        Settings(DEFAULT_MIN_OBSERVATIONS=0)


def test_video_analyzer_consensus_enforcement():
    """Verify OfflineVideoAnalyzer enforces min_observations before granting official worker status."""
    import numpy as np
    from openset_reid.pipeline.video_analyzer import OfflineVideoAnalyzer, IdentityStatus

    analyzer = OfflineVideoAnalyzer(
        score_threshold=0.85,
        contrast_margin=0.10,
        min_observations=3,
        policy_id="POL-ALERTING-V1"
    )
    dummy_vec = np.zeros(512, dtype=np.float32)
    dummy_vec[0] = 1.0
    analyzer.matcher.enroll("WORKER_ALPHA", dummy_vec)

    fake_frame = np.random.RandomState(42).randint(0, 255, (100, 100, 3), dtype=np.uint8)
    boxes = [(10, 10, 30, 70)]
    analyzer.update_tracks(fake_frame, boxes, frame_idx=1)

    assert len(analyzer.active_tracks) == 1
    t1 = analyzer.active_tracks[0]
    assert t1["identity_status"] != IdentityStatus.OFFICIAL_WORKER.value
    assert t1["matched_identity"] is None

