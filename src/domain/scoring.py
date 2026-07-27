"""
Scoring logic for OKRs based on Google re:Work documentation.
Scores are normalized to 0.0 - 1.0.
"""

from __future__ import annotations

from typing import Any, List, Optional, Sequence

EPSILON = 1e-9


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp value between min and max."""
    return max(min_val, min(max_val, value))


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return float(default)
    if numeric != numeric:  # NaN
        return float(default)
    return numeric


def _normalize_metric_type(metric_type: Any) -> str:
    raw = getattr(metric_type, "value", metric_type)
    token = str(raw or "").strip().upper()
    if token in {"BOOLEAN", "BOOL"}:
        return "BOOLEAN"
    if token in {"PERCENT", "PCT", "PERCENTAGE"}:
        return "PERCENT"
    return "NUMERIC"


def normalize_weights(
    weights: Optional[Sequence[float]], *, count: int
) -> Optional[List[float]]:
    """
    Normalize sibling weights so they sum to 1.0.
    Returns equal weights if all provided values are zero/invalid.
    """
    if not weights or count <= 0 or len(weights) != count:
        return None

    cleaned = [max(0.0, _coerce_float(weight, default=0.0)) for weight in weights]
    total_weight = sum(cleaned)
    if total_weight < EPSILON:
        equal = 1.0 / float(count)
        return [equal for _ in range(count)]
    return [weight / total_weight for weight in cleaned]


def calculate_kr_score(
    current: float, target: float, start: float = 0.0, metric_type: str = "numeric"
) -> float:
    """
    Calculate normalized score (0.0 - 1.0) for a Key Result.

    re:Work logic:
    - Numeric: (current - start) / (target - start)
    - Boolean: 1.0 if done else 0.0
    - Percent: current / 100.0 (if target is 100) or standard numeric formula.
    """
    metric_kind = _normalize_metric_type(metric_type)
    current_value = _coerce_float(current, default=0.0)
    target_value = _coerce_float(target, default=100.0)
    start_value = _coerce_float(start, default=0.0)

    if metric_kind == "BOOLEAN":
        # Any current_value >= target_value is considered done for boolean
        return 1.0 if current_value >= target_value else 0.0

    if (
        metric_kind == "PERCENT"
        and abs(start_value) < EPSILON
        and abs(target_value - 100.0) < EPSILON
    ):
        return clamp(current_value / 100.0, 0.0, 1.0)

    denominator = target_value - start_value
    if abs(denominator) < EPSILON:
        # No range to traverse; treat exact target hit as complete.
        return 1.0 if abs(current_value - target_value) < EPSILON else 0.0

    # Direction-aware by construction:
    # - Incremental KR: target > start
    # - Decremental KR: target < start
    score = (current_value - start_value) / denominator
    return clamp(score, 0.0, 1.0)


def calculate_objective_score(
    kr_scores: List[float],
    weights: Optional[List[float]] = None,
    weighted: bool = False,
) -> float:
    """
    Calculate objective score by averaging KR scores.
    """
    if not kr_scores:
        return 0.0

    if not weighted:
        return sum(kr_scores) / len(kr_scores)

    normalized_weights = normalize_weights(weights, count=len(kr_scores))
    if not normalized_weights:
        return sum(kr_scores) / len(kr_scores)

    weighted_sum = sum(
        score * weight for score, weight in zip(kr_scores, normalized_weights)
    )
    return weighted_sum


def calculate_goal_score(
    objective_scores: List[float], weights: Optional[List[float]] = None
) -> float:
    """
    Calculate goal score by aggregating objective scores.
    Supports weighted average if weights are provided.
    """
    if not objective_scores:
        return 0.0

    normalized_weights = normalize_weights(weights, count=len(objective_scores))
    if not normalized_weights:
        return sum(objective_scores) / len(objective_scores)

    weighted_sum = sum(
        score * weight for score, weight in zip(objective_scores, normalized_weights)
    )
    return weighted_sum


def get_score_color_band(score: float) -> str:
    """
    Return color band CSS class based on re:Work spec:
    0.0 - 0.3: Red
    0.4 - 0.6: Yellow
    0.7 - 0.9: Green
    1.0: Blue
    """
    if score >= 1.0:
        return "atlas-score-band-blue"
    if score >= 0.7:
        return "atlas-score-band-green"
    if score >= 0.4:
        return "atlas-score-band-yellow"
    return "atlas-score-band-red"


def get_score_label(score: float) -> str:
    """Return descriptive label for score."""
    if score >= 1.0:
        return "Superstar (Possible Sandbagger)"
    if score >= 0.7:
        return "On Track"
    if score >= 0.4:
        return "At Risk"
    return "Missed"
