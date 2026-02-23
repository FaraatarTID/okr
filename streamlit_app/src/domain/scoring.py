"""
Scoring logic for OKRs based on Google re:Work documentation.
Scores are normalized to 0.0 - 1.0.
"""

from typing import List, Optional


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp value between min and max."""
    return max(min_val, min(max_val, value))


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
    if metric_type == "boolean":
        # Any current_value >= target_value is considered done for boolean
        return 1.0 if current >= target else 0.0

    denominator = target - start
    if abs(denominator) < 1e-9:
        # Avoid division by zero. If target == start, it's either 1.0 if met or 0.0.
        return 1.0 if current >= target else 0.0

    score = (current - start) / denominator
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

    if not weighted or not weights or len(weights) != len(kr_scores):
        return sum(kr_scores) / len(kr_scores)

    total_weight = sum(weights)
    if total_weight < 1e-9:
        return sum(kr_scores) / len(kr_scores)

    weighted_sum = sum(s * w for s, w in zip(kr_scores, weights))
    return weighted_sum / total_weight


def calculate_goal_score(
    objective_scores: List[float], weights: Optional[List[float]] = None
) -> float:
    """
    Calculate goal score by aggregating objective scores.
    Supports weighted average if weights are provided.
    """
    if not objective_scores:
        return 0.0

    if not weights or len(weights) != len(objective_scores):
        return sum(objective_scores) / len(objective_scores)

    total_weight = sum(weights)
    if total_weight < 1e-9:
        return sum(objective_scores) / len(objective_scores)

    weighted_sum = sum(s * w for s, w in zip(objective_scores, weights))
    return weighted_sum / total_weight


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
