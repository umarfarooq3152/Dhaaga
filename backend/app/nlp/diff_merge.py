"""Pure session-state merge logic — no I/O, table-driven unit tests live here."""

from datetime import date, timedelta

from app.schemas.session import IntentExtractionResult, SessionState


def _dedup(items: list[str]) -> list[str]:
    """Deduplicate case-insensitively while preserving first-seen order/casing."""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = item.lower().strip()
        if key and key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _deadline_from_urgency(urgency_days: int) -> date:
    return date.today() + timedelta(days=urgency_days)


def merge_session_state(
    current: SessionState, diff: IntentExtractionResult
) -> SessionState:
    """Merge an LLM/fast-path diff into the current session state.

    Rules (TDD §6):
    - occasion/color_preference/size/budget_max: explicit new values overwrite.
    - style_descriptors/excluded: accumulate rather than overwrite.
    - A clear topic change (occasion changes) resets deadline_date but keeps
      size/budget_max.
    - brands is untouched here — only mutated by the fast-path "different
      brand" rule, not by LLM diffs, in this phase.
    """
    topic_changed = diff.occasion is not None and diff.occasion != current.occasion

    if diff.urgency_days is not None:
        deadline_date = _deadline_from_urgency(diff.urgency_days)
    elif topic_changed:
        deadline_date = None
    else:
        deadline_date = current.deadline_date

    return SessionState(
        occasion=diff.occasion if diff.occasion is not None else current.occasion,
        color_preference=(
            diff.color_preference
            if diff.color_preference is not None
            else current.color_preference
        ),
        budget_max=(
            diff.budget_max if diff.budget_max is not None else current.budget_max
        ),
        style_descriptors=_dedup(current.style_descriptors + diff.style_descriptors),
        size=current.size if diff.size is None else diff.size,
        deadline_date=deadline_date,
        excluded=_dedup(current.excluded + diff.excluded),
        brands=current.brands,
        department=current.department,
    )
