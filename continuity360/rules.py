"""Framework-independent domain rules; recovery durations are measured in minutes."""

import math
import re
from datetime import date


def next_bcp_version(previous: str, revision_type: str) -> str:
    if not isinstance(previous, str) or not re.fullmatch(r"[1-9][0-9]*\.(0|[1-9][0-9]*)", previous):
        raise ValueError("The previous plan version must be a major.minor number.")
    if revision_type not in ("Minor", "Major"):
        raise ValueError("Choose a Minor or Major revision.")
    major, minor = map(int, previous.split("."))
    return f"{major + 1}.0" if revision_type == "Major" else f"{major}.{minor + 1}"


def number(value: object, label: str, *, minimum: float = 0) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a finite number.")
    try:
        result = float(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{label} must be a finite number.") from exc
    if not math.isfinite(result) or result < minimum:
        raise ValueError(f"{label} must be finite and at least {minimum:g}.")
    return result


def risk_score(likelihood: object, impact: object) -> tuple[int, str]:
    values = [number(likelihood, "Likelihood", minimum=1), number(impact, "Impact", minimum=1)]
    if any(value > 5 or not value.is_integer() for value in values):
        raise ValueError("Likelihood and impact must be whole numbers from 1 to 5.")
    score = int(values[0] * values[1])
    rating = "Critical" if score >= 20 else "High" if score >= 12 else "Medium" if score >= 6 else "Low"
    return score, rating


def recovery_objectives(rto: object, rpo: object, mtpd: object) -> tuple[float, float, float]:
    values = (
        number(rto, "RTO"),
        number(rpo, "RPO"),
        number(mtpd, "MTPD", minimum=1),
    )
    if values[0] >= values[2]:
        raise ValueError("RTO must be less than MTPD, leaving time for business recovery.")
    # RPO is a data-loss tolerance, not a restoration duration; it is not ordered against RTO.
    return values


def date_order(start: date, end: date, label: str) -> None:
    if end < start:
        raise ValueError(f"{label} must not be before its start date.")


def review_reminder_slot(review_date: date, today: date) -> str | None:
    days = (review_date - today).days
    if days > 30:
        return None
    if days > 7:
        return "before-30"
    if days > 1:
        return "before-7"
    if days >= 0:
        return "before-1"
    return f"overdue-{(-days - 1) // 7 + 1}"
