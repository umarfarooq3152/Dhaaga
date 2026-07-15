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
