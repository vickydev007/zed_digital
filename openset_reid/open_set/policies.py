from dataclasses import dataclass, asdict
from enum import Enum
from typing import Dict, Any, Optional


class PolicyID(str, Enum):
    POL_SUPERVISED_V1 = "POL-SUPERVISED-V1"
    POL_ALERTING_V1 = "POL-ALERTING-V1"
    POL_AUTONOMOUS_V1 = "POL-AUTONOMOUS-V1"


@dataclass(frozen=True)
class OperationalPolicy:
    policy_id: str
    name: str
    target_scope: str
    tau: float
    delta: float
    min_obs: int
    operator_role: str
    target_tar_percent: float
    target_far_percent: float
    status: str
    requires_human_verification: bool
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


OPERATIONAL_POLICIES: Dict[str, OperationalPolicy] = {
    PolicyID.POL_SUPERVISED_V1.value: OperationalPolicy(
        policy_id=PolicyID.POL_SUPERVISED_V1.value,
        name="Policy A: Supervised CCTV Investigation",
        target_scope="CCTV Video Investigation / Forensic Operator Review",
        tau=0.70,
        delta=0.04,
        min_obs=1,
        operator_role="Human investigator reviews every candidate match",
        target_tar_percent=100.0,
        target_far_percent=42.2,
        status="AUTHORIZED_SUPERVISED",
        requires_human_verification=True,
        description=(
            "Designed for maximum genuine recall during post-incident investigation. "
            "Single-frame candidate generation with permissive threshold tau=0.70. "
            "Operator must manually inspect and confirm identity before taking action."
        )
    ),
    PolicyID.POL_ALERTING_V1.value: OperationalPolicy(
        policy_id=PolicyID.POL_ALERTING_V1.value,
        name="Policy B: Security Operator Alerting (Active Default)",
        target_scope="Live Security Operations / Multi-Observation Track Consensus",
        tau=0.85,
        delta=0.10,
        min_obs=3,
        operator_role="Security officer dispatched on confirmed track alert",
        target_tar_percent=84.0,
        target_far_percent=4.0,
        status="AUTHORIZED_CONDITIONAL",
        requires_human_verification=True,
        description=(
            "Active live surveillance default. Requires multi-frame pooled embedding "
            "across >= 3 observations with strict similarity tau >= 0.85 and contrast "
            "margin delta >= 0.10. Mitigates low-variance uniform bias."
        )
    ),
    PolicyID.POL_AUTONOMOUS_V1.value: OperationalPolicy(
        policy_id=PolicyID.POL_AUTONOMOUS_V1.value,
        name="Policy C: Autonomous Access Control",
        target_scope="Unattended Restricted Turnstiles / Door Access",
        tau=0.88,
        delta=0.12,
        min_obs=5,
        operator_role="Fully autonomous decision (Zero human intervention)",
        target_tar_percent=90.0,
        target_far_percent=0.0,
        status="RESTRICTED_BLOCKED",
        requires_human_verification=False,
        description=(
            "Zero-impostor-tolerance policy reserved for unattended physical access gates. "
            "Strictly GATED and RESTRICTED from production until high-assurance hardware "
            "and multi-modal biometrics meet predefined enterprise compliance limits."
        )
    ),
}

DEFAULT_POLICY_ID = PolicyID.POL_ALERTING_V1.value


def get_policy(policy_id: Optional[str] = None) -> OperationalPolicy:
    """Retrieve an immutable operational policy by identifier."""
    pid = policy_id or DEFAULT_POLICY_ID
    if pid not in OPERATIONAL_POLICIES:
        raise ValueError(
            f"Unknown operational policy: '{policy_id}'. Available: {list(OPERATIONAL_POLICIES.keys())}"
        )
    return OPERATIONAL_POLICIES[pid]


def list_policies() -> Dict[str, Dict[str, Any]]:
    """List all registered operational policies as dictionary."""
    return {pid: policy.to_dict() for pid, policy in OPERATIONAL_POLICIES.items()}
