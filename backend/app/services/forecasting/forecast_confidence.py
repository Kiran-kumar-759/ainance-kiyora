from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from statistics import mean, stdev

from app.schemas.forecasting import ConfidenceLabel


@dataclass(frozen=True)
class ConfidenceAssessment:
    label: ConfidenceLabel
    score: Decimal
    uncertainty_band_pct: Decimal


def assess_forecast_confidence(
    *,
    observation_count: int,
    coverage_days: int,
    monthly_totals: list[Decimal],
    horizon_days: int,
    has_confirmed_schedules: bool = False,
) -> ConfidenceAssessment:
    """
    Derive an empirical confidence classification from measurable historical coverage,
    observation count, spending stability (CV), and horizon length.
    Never returns arbitrary percentages or guesses when data is insufficient.
    """
    if observation_count < 3 or (coverage_days < 14 and not has_confirmed_schedules):
        return ConfidenceAssessment(
            label="insufficient_data",
            score=Decimal("0.0000"),
            uncertainty_band_pct=Decimal("0.00"),
        )

    score = 0.30
    # Coverage contribution (up to +0.28)
    if coverage_days >= 180:
        score += 0.28
    elif coverage_days >= 90:
        score += 0.22
    elif coverage_days >= 45:
        score += 0.14
    else:
        score += 0.06

    # Observation count contribution (up to +0.18)
    if observation_count >= 40:
        score += 0.18
    elif observation_count >= 15:
        score += 0.12
    else:
        score += 0.05

    # Volatility contribution using coefficient of variation (up to +0.16)
    vals = [float(v) for v in monthly_totals if v > Decimal("0.00")]
    cv = 0.50
    if len(vals) >= 2 and mean(vals) > 0:
        cv = stdev(vals) / mean(vals)
        if cv <= 0.18:
            score += 0.16
        elif cv <= 0.35:
            score += 0.10
        elif cv <= 0.60:
            score += 0.04
    elif has_confirmed_schedules:
        cv = 0.20
        score += 0.10

    if has_confirmed_schedules:
        score += 0.06

    # Long horizon decay
    if horizon_days >= 365:
        score -= 0.18
    elif horizon_days >= 180:
        score -= 0.10
    elif horizon_days >= 90:
        score -= 0.04

    clamped = max(0.15, min(0.95, score))
    dec_score = Decimal(str(round(clamped, 4)))

    if horizon_days >= 365 and coverage_days < 90 and not has_confirmed_schedules:
        return ConfidenceAssessment(
            label="low",
            score=Decimal(str(round(min(clamped, 0.38), 4))),
            uncertainty_band_pct=Decimal("35.00"),
        )

    if clamped >= 0.72:
        label: ConfidenceLabel = "high"
        band_pct = Decimal(str(round(min(22.0, max(8.0, cv * 45.0)), 2)))
    elif clamped >= 0.48:
        label = "medium"
        band_pct = Decimal(str(round(min(32.0, max(15.0, cv * 60.0)), 2)))
    else:
        label = "low"
        band_pct = Decimal("35.00")

    return ConfidenceAssessment(label=label, score=dec_score, uncertainty_band_pct=band_pct)


def apply_confidence_bounds(
    amount: Decimal | None, band_pct: Decimal
) -> tuple[Decimal | None, Decimal | None]:
    if amount is None:
        return None, None
    ratio = band_pct / Decimal("100")
    low = max(Decimal("0.00"), (amount * (Decimal("1.00") - ratio))).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    high = (amount * (Decimal("1.00") + ratio)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return low, high
