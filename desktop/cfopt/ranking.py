from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

from .models import DomainMetric


def _round_one(value: float) -> float:
    return round(value * 10.0) / 10.0


def address_floor(speeds: list[float], failed_count: int) -> float:
    if failed_count > 0:
        return 0.0
    valid = [item for item in speeds if item > 0.0 and math.isfinite(item)]
    return min(valid) if valid else 0.0


def success_rate(successes: int, total: int) -> float:
    return 0.0 if total <= 0 else _round_one(successes * 100.0 / total)


def median_ttfb(values: list[float]) -> float:
    valid = sorted(item for item in values if item > 0.0 and math.isfinite(item))
    return statistics.median(valid) if valid else -1.0


def variation(speeds: list[float]) -> float:
    values = [item for item in speeds if item >= 0.0 and math.isfinite(item)]
    if len(values) < 2:
        return 0.0
    average = statistics.fmean(values)
    if average <= 0.0:
        return 0.0
    return _round_one((max(values) - min(values)) * 100.0 / average)


def stability_label(variation_pct: float, success_rate_pct: float) -> str:
    if success_rate_pct >= 90.0 and variation_pct <= 15.0:
        return "优秀"
    if success_rate_pct >= 75.0 and variation_pct <= 30.0:
        return "良好"
    if success_rate_pct >= 50.0:
        return "一般"
    return "较差"


def rank(metrics: list[DomainMetric]) -> list[DomainMetric]:
    return sorted(
        metrics,
        key=lambda item: (
            -item.address_floor_mbps,
            -item.success_rate_pct,
            -item.min_complete_mbps,
            -item.avg_complete_mbps,
            -item.address_success_rate_pct,
            item.variation_pct,
            item.median_ttfb_ms if item.median_ttfb_ms >= 0.0 else math.inf,
        ),
    )


def rank_asia(metrics: list[DomainMetric]) -> list[DomainMetric]:
    return sorted(
        metrics,
        key=lambda item: (
            -item.edge_score,
            item.pop_drift,
            -item.address_floor_mbps,
            -item.success_rate_pct,
            -item.min_complete_mbps,
            -item.avg_complete_mbps,
            item.variation_pct,
            item.median_ttfb_ms if item.median_ttfb_ms >= 0.0 else math.inf,
        ),
    )


@dataclass(frozen=True)
class BaselineComparison:
    decision: str
    floor_gain_pct: float
    minimum_gain_pct: float
    average_gain_pct: float
    reliability_not_worse: bool
    stability_not_worse: bool


def compare_to_baseline(
    challenger: DomainMetric,
    baseline: DomainMetric,
    required_gain_pct: float = 10.0,
    allowed_variation_worse_points: float = 5.0,
) -> BaselineComparison:
    def gain(value: float, base: float) -> float:
        return (value - base) * 100.0 / base if base > 0.0 else math.nan

    floor_gain = gain(challenger.address_floor_mbps, baseline.address_floor_mbps)
    minimum_gain = gain(challenger.min_complete_mbps, baseline.min_complete_mbps)
    average_gain = gain(challenger.avg_complete_mbps, baseline.avg_complete_mbps)
    reliability_ok = (
        challenger.success_rate_pct + 1e-9 >= baseline.success_rate_pct
        and challenger.address_success_rate_pct + 1e-9 >= baseline.address_success_rate_pct
    )
    stability_ok = challenger.variation_pct <= baseline.variation_pct + allowed_variation_worse_points + 1e-9
    baseline_valid = (
        baseline.address_floor_mbps > 0.0
        and baseline.min_complete_mbps > 0.0
        and baseline.avg_complete_mbps > 0.0
        and baseline.success_rate_pct > 0.0
        and baseline.address_success_rate_pct > 0.0
    )
    beats_clearly = (
        baseline_valid
        and floor_gain >= required_gain_pct - 1e-9
        and minimum_gain >= required_gain_pct - 1e-9
        and average_gain >= required_gain_pct - 1e-9
        and reliability_ok
        and stability_ok
    )
    better_but_not_enough = (
        baseline_valid
        and floor_gain > 0.0
        and minimum_gain > 0.0
        and average_gain > 0.0
        and reliability_ok
        and stability_ok
    )
    decision = "REPLACE" if beats_clearly else "OBSERVE" if (not baseline_valid or better_but_not_enough) else "KEEP"
    return BaselineComparison(
        decision,
        floor_gain,
        minimum_gain,
        average_gain,
        reliability_ok,
        stability_ok,
    )
