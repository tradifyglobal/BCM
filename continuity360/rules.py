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


def call_tree_structure(members: list, require_complete: bool) -> None:
    """members is a list of (contact, called_by) pairs; called_by None starts the cascade."""
    contacts = [contact for contact, _caller in members]
    if len(set(contacts)) != len(contacts):
        raise ValueError("Each contact may appear in the call tree only once.")
    known = set(contacts)
    for contact, caller in members:
        if caller == contact:
            raise ValueError("A contact cannot call themselves.")
        if caller is not None and caller not in known:
            raise ValueError("Every 'called by' entry must be another member of this call tree.")
    if not require_complete:
        return
    if len(members) < 2:
        raise ValueError("An active call tree needs at least two members.")
    roots = [contact for contact, caller in members if caller is None]
    if not roots:
        raise ValueError("An active call tree needs an initiator with no 'called by' entry.")
    children: dict = {}
    for contact, caller in members:
        if caller is not None:
            children.setdefault(caller, []).append(contact)
    reached, queue = set(roots), list(roots)
    while queue:
        for follower in children.get(queue.pop(), ()):
            if follower not in reached:
                reached.add(follower)
                queue.append(follower)
    if reached != known:
        raise ValueError("Every member of an active call tree must be reachable from an "
                         "initiator; remove circular or orphaned 'called by' entries.")


def call_tree_span(members: list, limit: int = 7) -> list:
    """Callers phoning more than `limit` people; good practice is three to seven per caller."""
    known = {contact for contact, _caller in members}
    counts: dict = {}
    for contact, caller in members:
        if caller in known and caller != contact:
            counts[caller] = counts.get(caller, 0) + 1
    return sorted((caller, count) for caller, count in counts.items() if count > limit)


def incident_lifecycle(status: str, detected_on: object, resolved_on: object,
                       resolution_summary: object) -> None:
    """Resolved and closed incidents must carry their resolution evidence."""
    if status not in ("Resolved", "Closed"):
        return
    if not resolved_on:
        raise ValueError("Record when the incident was resolved before resolving or closing it.")
    if detected_on and str(resolved_on) < str(detected_on):
        raise ValueError("The resolution time cannot be before the detection time.")
    if not str(resolution_summary or "").strip():
        raise ValueError("Record a resolution summary before resolving or closing an incident.")


def crisis_closure(status: str, declared_on: object, stood_down_on: object,
                   outcome_summary: object) -> None:
    """Stood-down and closed crises must record when and with what outcome."""
    if status not in ("Stood Down", "Closed"):
        return
    if not stood_down_on:
        raise ValueError("Record when the crisis was stood down before closing it.")
    if declared_on and str(stood_down_on) < str(declared_on):
        raise ValueError("The stand-down time cannot be before the declaration time.")
    if not str(outcome_summary or "").strip():
        raise ValueError("Record an outcome summary before standing down or closing a crisis.")


def dependency_target(application: object, depends_on_application: object,
                      depends_on_server: object, depends_on_database: object) -> None:
    """A dependency names exactly one target component and never the application itself."""
    targets = [t for t in (depends_on_application, depends_on_server, depends_on_database) if t]
    if len(targets) != 1:
        raise ValueError("Select exactly one component this application depends on.")
    if depends_on_application and depends_on_application == application:
        raise ValueError("An application cannot depend on itself.")


def exercise_completion(status: str, conducted_on: object, result: object, summary: object,
                        objective_outcomes: list) -> None:
    """A completed exercise must carry its evidence; other statuses are unrestricted."""
    if status != "Completed":
        return
    if not conducted_on:
        raise ValueError("Record the conducted date before completing an exercise.")
    if not result:
        raise ValueError("Record the overall result before completing an exercise.")
    if not str(summary or "").strip():
        raise ValueError("Record a results summary before completing an exercise.")
    if not objective_outcomes or any(
            outcome in (None, "", "Not Assessed") for outcome in objective_outcomes):
        raise ValueError("Assess every objective before completing an exercise.")


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
