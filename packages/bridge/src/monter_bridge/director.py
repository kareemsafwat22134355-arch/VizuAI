from __future__ import annotations

from .planning_models import DirectorPlan, DirectorSection, EditRole


DEFAULT_ENERGY_CURVE = [
    0.18, 0.22, 0.28, 0.38,
    0.50, 0.64, 0.78, 0.90,
    0.30, 0.48, 0.68, 0.84,
    0.96, 0.74, 0.20, 0.88,
    0.46,
]


def default_director_plan(target_duration_seconds: float = 15.0) -> DirectorPlan:
    return DirectorPlan(
        target_duration_seconds=target_duration_seconds,
        energy_curve=DEFAULT_ENERGY_CURVE,
        sections=[
            DirectorSection(role="setup", start_normalized=0.00, end_normalized=0.16),
            DirectorSection(role="promise", start_normalized=0.16, end_normalized=0.30),
            DirectorSection(role="build", start_normalized=0.30, end_normalized=0.52),
            DirectorSection(role="escalate", start_normalized=0.52, end_normalized=0.64),
            DirectorSection(role="rupture", start_normalized=0.64, end_normalized=0.70),
            DirectorSection(role="reveal", start_normalized=0.70, end_normalized=0.80),
            DirectorSection(role="barrage", start_normalized=0.80, end_normalized=0.91),
            DirectorSection(role="vacuum", start_normalized=0.91, end_normalized=0.96),
            DirectorSection(role="payoff", start_normalized=0.96, end_normalized=1.00),
        ],
        restrictions=[
            "Do not cut on every beat.",
            "Prefer motion-aware source anchors over arbitrary trims.",
            "Avoid immediate repetition when an alternative shot is viable.",
            "Preserve at least one deliberate low-energy rupture before the payoff.",
            "Hard cuts remain valid when continuity is already strong.",
        ],
    )


def energy_at(plan: DirectorPlan, normalized_time: float) -> float:
    normalized_time = max(0.0, min(1.0, normalized_time))
    curve = plan.energy_curve
    if len(curve) == 1:
        return curve[0]
    position = normalized_time * (len(curve) - 1)
    left = int(position)
    right = min(len(curve) - 1, left + 1)
    fraction = position - left
    return curve[left] * (1 - fraction) + curve[right] * fraction


def role_at(plan: DirectorPlan, normalized_time: float) -> EditRole:
    normalized_time = max(0.0, min(0.999999, normalized_time))
    for section in plan.sections:
        if section.start_normalized <= normalized_time < section.end_normalized:
            return section.role
    return plan.sections[-1].role
