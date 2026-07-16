"""Table-driven tests for session-state diff-merge rules."""

from datetime import date, timedelta

from app.nlp.diff_merge import merge_session_state
from app.schemas.session import IntentExtractionResult, SessionState


def test_fresh_session_takes_all_diff_fields():
    current = SessionState()
    diff = IntentExtractionResult(
        occasion="eid",
        budget_max=20000,
        style_descriptors=["elegant"],
        assistant_reply="ok",
    )
    result = merge_session_state(current, diff)
    assert result.occasion == "eid"
    assert result.budget_max == 20000
    assert result.style_descriptors == ["elegant"]


def test_style_descriptors_accumulate_across_turns():
    current = SessionState(style_descriptors=["silk"])
    diff = IntentExtractionResult(style_descriptors=["elegant"], assistant_reply="ok")
    result = merge_session_state(current, diff)
    assert result.style_descriptors == ["silk", "elegant"]


def test_style_descriptors_dedupe_case_insensitively():
    current = SessionState(style_descriptors=["Silk"])
    diff = IntentExtractionResult(style_descriptors=["silk", "formal"], assistant_reply="ok")
    result = merge_session_state(current, diff)
    assert result.style_descriptors == ["Silk", "formal"]


def test_excluded_accumulates():
    current = SessionState(excluded=["limelight"])
    diff = IntentExtractionResult(excluded=["zellbury"], assistant_reply="ok")
    result = merge_session_state(current, diff)
    assert result.excluded == ["limelight", "zellbury"]


def test_negative_style_evidence_persists_and_positive_request_cancels_it():
    current = SessionState(excluded_styles=["embellished"])
    kept = merge_session_state(
        current,
        IntentExtractionResult(assistant_reply="ok", color_preference="green"),
    )
    restored = merge_session_state(
        kept,
        IntentExtractionResult(
            assistant_reply="ok", style_descriptors=["embellished"]
        ),
    )

    assert kept.excluded_styles == ["embellished"]
    assert restored.excluded_styles == []


def test_color_preference_overwrites_not_accumulates():
    current = SessionState(color_preference="red")
    diff = IntentExtractionResult(color_preference="blue", assistant_reply="ok")
    result = merge_session_state(current, diff)
    assert result.color_preference == "blue"


def test_budget_max_overwrites_when_present():
    current = SessionState(budget_max=50000)
    diff = IntentExtractionResult(budget_max=30000, assistant_reply="ok")
    result = merge_session_state(current, diff)
    assert result.budget_max == 30000


def test_budget_max_kept_when_diff_has_none():
    current = SessionState(budget_max=50000)
    diff = IntentExtractionResult(assistant_reply="ok")
    result = merge_session_state(current, diff)
    assert result.budget_max == 50000


def test_explicit_clear_fields_remove_only_requested_constraints():
    current = SessionState(
        occasion="eid", category="shirt", color_preference="pink",
        budget_max=8000, style_descriptors=["striped", "formal"], size="M",
    )

    result = merge_session_state(
        current,
        IntentExtractionResult(
            clear_fields=["occasion", "style", "budget"], assistant_reply="ok"
        ),
    )

    assert result.occasion is None
    assert result.style_descriptors == []
    assert result.budget_max is None
    assert result.category == "shirt"
    assert result.color_preference == "pink"
    assert result.size == "M"


def test_specific_style_removal_keeps_other_style_constraints():
    current = SessionState(
        category="shirt", color_preference="pink",
        style_descriptors=["striped", "formal"],
    )

    result = merge_session_state(
        current,
        IntentExtractionResult(remove_styles=["striped"], assistant_reply="ok"),
    )

    assert result.category == "shirt"
    assert result.color_preference == "pink"
    assert result.style_descriptors == ["formal"]


def test_topic_change_resets_deadline_but_keeps_size_and_budget():
    current = SessionState(
        occasion="mehndi",
        size="M",
        budget_max=40000,
        deadline_date=date.today() + timedelta(days=3),
    )
    diff = IntentExtractionResult(occasion="wedding", assistant_reply="ok")
    result = merge_session_state(current, diff)
    assert result.occasion == "wedding"
    assert result.deadline_date is None
    assert result.size == "M"
    assert result.budget_max == 40000


def test_topic_change_resets_style_descriptors():
    # Real bug: style_descriptors accumulated forever with no reset, so
    # the displayed "Style" chip (showing the oldest word) stayed stuck
    # on the first-ever descriptor even after the shopper moved on to a
    # genuinely different occasion.
    current = SessionState(occasion="wedding", style_descriptors=["traditional", "embroidered"])
    diff = IntentExtractionResult(occasion="casual", style_descriptors=["minimal"], assistant_reply="ok")
    result = merge_session_state(current, diff)
    assert result.occasion == "casual"
    assert result.style_descriptors == ["minimal"]


def test_same_occasion_repeated_still_accumulates_style_descriptors():
    current = SessionState(occasion="wedding", style_descriptors=["traditional"])
    diff = IntentExtractionResult(occasion="wedding", style_descriptors=["embroidered"], assistant_reply="ok")
    result = merge_session_state(current, diff)
    assert result.style_descriptors == ["traditional", "embroidered"]


def test_topic_change_with_no_new_style_descriptors_clears_old_ones():
    current = SessionState(occasion="wedding", style_descriptors=["traditional", "embroidered"])
    diff = IntentExtractionResult(occasion="casual", assistant_reply="ok")
    result = merge_session_state(current, diff)
    assert result.style_descriptors == []


def test_same_occasion_repeated_does_not_reset_deadline():
    deadline = date.today() + timedelta(days=3)
    current = SessionState(occasion="mehndi", deadline_date=deadline)
    diff = IntentExtractionResult(occasion="mehndi", assistant_reply="ok")
    result = merge_session_state(current, diff)
    assert result.deadline_date == deadline


def test_urgency_days_sets_deadline_date():
    current = SessionState()
    diff = IntentExtractionResult(urgency_days=5, assistant_reply="ok")
    result = merge_session_state(current, diff)
    assert result.deadline_date == date.today() + timedelta(days=5)


def test_size_overwrites_when_present_kept_when_absent():
    current = SessionState(size="M")
    result = merge_session_state(current, IntentExtractionResult(size="L", assistant_reply="ok"))
    assert result.size == "L"

    result2 = merge_session_state(current, IntentExtractionResult(assistant_reply="ok"))
    assert result2.size == "M"


def test_brands_untouched_by_llm_diff():
    current = SessionState(brands=["limelight"])
    diff = IntentExtractionResult(occasion="eid", assistant_reply="ok")
    result = merge_session_state(current, diff)
    assert result.brands == ["limelight"]


def test_department_persists_across_merge():
    # department isn't part of IntentExtractionResult at all (it comes from
    # onboarding, not free text) — merge_session_state must explicitly carry
    # it forward or every turn after the first would silently drop it back
    # to None, exactly like `brands` needs the same explicit carry-forward.
    current = SessionState(department="men")
    diff = IntentExtractionResult(occasion="eid", budget_max=20000, assistant_reply="ok")
    result = merge_session_state(current, diff)
    assert result.department == "men"


def test_explicit_department_overwrites_and_persists():
    current = SessionState(department="men", occasion="wedding")
    changed = merge_session_state(
        current, IntentExtractionResult(department="women", assistant_reply="ok")
    )
    assert changed.department == "women"
    persisted = merge_session_state(changed, IntentExtractionResult(assistant_reply="ok"))
    assert persisted.department == "women"


def test_child_age_overwrites_and_then_persists():
    current = SessionState(wants_kids=True, child_age_months=24)
    changed = merge_session_state(
        current,
        IntentExtractionResult(child_age_months=36, assistant_reply="ok"),
    )
    assert changed.child_age_months == 36

    persisted = merge_session_state(changed, IntentExtractionResult(assistant_reply="ok"))
    assert persisted.child_age_months == 36


def test_semantic_query_and_constraint_roles_persist_across_refinements():
    first = merge_session_state(
        SessionState(),
        IntentExtractionResult(
            semantic_query="women's festive mehndi outfit",
            hard_constraints=["department", "occasion"],
            soft_preferences=["color_preference"],
            assistant_reply="ok",
        ),
    )
    refined = merge_session_state(
        first,
        IntentExtractionResult(
            semantic_query="women's green festive mehndi outfit",
            hard_constraints=["color_preference"],
            soft_preferences=["occasion", "style_descriptors"],
            assistant_reply="ok",
        ),
    )

    assert refined.semantic_query == "women's green festive mehndi outfit"
    assert refined.hard_constraints == [
        "department", "occasion", "color_preference"
    ]
    assert refined.soft_preferences == ["style_descriptors"]


def test_clearing_a_field_also_clears_its_constraint_role():
    current = SessionState(
        color_preference="blue",
        hard_constraints=["color_preference", "department"],
        soft_preferences=["occasion"],
    )
    result = merge_session_state(
        current,
        IntentExtractionResult(clear_fields=["color"], assistant_reply="ok"),
    )

    assert result.color_preference is None
    assert result.hard_constraints == ["department"]
