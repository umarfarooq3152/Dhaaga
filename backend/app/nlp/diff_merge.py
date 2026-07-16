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
    - style_descriptors/excluded: accumulate rather than overwrite *within
      the same topic* — a genuine topic change (occasion changes) resets
      style_descriptors along with deadline_date, since style words
      describing the old occasion ("traditional" for a wedding) don't
      carry over to a genuinely new one ("casual" for a daily-wear ask).
      Real bug this fixes: style_descriptors accumulated forever with no
      reset at all, so the displayed "Style" chip — which shows the
      *oldest* accumulated word — stayed stuck on whatever was said
      first, no matter how much the shopper's intent moved on.
    - brands is untouched here — only mutated by the fast-path "different
      brand" rule, not by LLM diffs, in this phase.
    """
    cleared = set(diff.clear_fields)
    topic_changed = diff.occasion is not None and diff.occasion != current.occasion

    if diff.urgency_days is not None:
        deadline_date = _deadline_from_urgency(diff.urgency_days)
    elif topic_changed:
        deadline_date = None
    else:
        deadline_date = current.deadline_date

    prior_style_descriptors = (
        [] if topic_changed or "style" in cleared else current.style_descriptors
    )
    removed_styles = {style.lower().strip() for style in diff.remove_styles}
    prior_style_descriptors = [
        style for style in prior_style_descriptors
        if style.lower().strip() not in removed_styles
    ]

    field_aliases = {
        "color": "color_preference",
        "budget": "budget_max",
        "style": "style_descriptors",
        "age": "child_age_months",
    }
    cleared_constraint_fields = {
        field_aliases.get(field, field) for field in cleared
    }
    prior_hard = [
        field for field in current.hard_constraints
        if field not in cleared_constraint_fields
    ]
    prior_soft = [
        field for field in current.soft_preferences
        if field not in cleared_constraint_fields
    ]
    hard_constraints = _dedup(prior_hard + list(diff.hard_constraints))
    hard_keys = {field.lower() for field in hard_constraints}
    soft_preferences = [
        field for field in _dedup(prior_soft + list(diff.soft_preferences))
        if field.lower() not in hard_keys
    ]
    prior_excluded_styles = [] if topic_changed else current.excluded_styles
    positive_styles = {style.lower().strip() for style in diff.style_descriptors}
    excluded_styles = _dedup([
        style for style in (*prior_excluded_styles, *diff.excluded_styles)
        if style.lower().strip() not in positive_styles
    ])

    return SessionState(
        occasion=(
            None if "occasion" in cleared
            else diff.occasion if diff.occasion is not None else current.occasion
        ),
        category=(
            None if "category" in cleared
            else diff.category if diff.category is not None else current.category
        ),
        color_preference=(
            None if "color" in cleared else diff.color_preference
            if diff.color_preference is not None
            else current.color_preference
        ),
        budget_max=(
            None if "budget" in cleared
            else diff.budget_max if diff.budget_max is not None else current.budget_max
        ),
        style_descriptors=_dedup(prior_style_descriptors + diff.style_descriptors),
        size=None if "size" in cleared else current.size if diff.size is None else diff.size,
        deadline_date=deadline_date,
        excluded=_dedup(current.excluded + diff.excluded),
        brands=current.brands,
        department=diff.department if diff.department is not None else current.department,
        wants_kids=diff.wants_kids if diff.wants_kids is not None else current.wants_kids,
        child_age_months=(
            None if "age" in cleared else diff.child_age_months
            if diff.child_age_months is not None
            else current.child_age_months
        ),
        semantic_query=diff.semantic_query.strip() or current.semantic_query,
        excluded_styles=excluded_styles,
        fallback_categories=_dedup(diff.fallback_categories) or current.fallback_categories,
        fallback_styles=_dedup(diff.fallback_styles) or current.fallback_styles,
        hard_constraints=hard_constraints,
        soft_preferences=soft_preferences,
    )
