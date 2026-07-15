"""Tests for the deterministic fast-path refinement classifier."""

import pytest

from app.kids_age import extract_child_age_months
from app.nlp.fast_path_classifier import classify, is_kids_request
from app.schemas.product import Product
from app.schemas.session import SessionState


def _product(id_, price, **kwargs) -> Product:
    defaults = dict(
        name="Test Product",
        description="A test product",
        image="https://example.com/1.jpg",
        product_url="https://example.com/products/1",
    )
    defaults.update(kwargs)
    return Product(id=id_, price=price, **defaults)


@pytest.fixture
def last_results() -> list[Product]:
    return [
        _product("limelight:1", 5000),
        _product("limelight:2", 3000),
        _product("alkaram:1", 15000),
    ]


def test_no_match_falls_through_to_none():
    assert classify("something totally unrelated to any pattern", SessionState(), []) is None


def test_is_kids_request_by_age():
    # Real bug: the LLM didn't reliably recognize "shopping for a child" on
    # its own, extracting a nonsensical size="kids" and surfacing adult
    # womenswear as if it matched a toddler's outfit. Detection now happens
    # deterministically, independent of whichever path (fast-path or LLM)
    # extracts the rest of the message (occasion/color/style).
    text = "I want to dress up my 2 year old daughter in something pink and traditional"
    assert is_kids_request(text) is True
    assert extract_child_age_months(text) == 24


def test_extracts_child_age_in_months():
    assert extract_child_age_months("an outfit for my 18 month old son") == 18


def test_does_not_extract_unrelated_duration_as_child_age():
    assert extract_child_age_months("I've been shopping here for 2 years") is None


def test_is_kids_request_by_keyword():
    for text in ["need a toddler outfit for eid", "looking for kids clothes", "something for my newborn"]:
        assert is_kids_request(text) is True, f"expected a kids-request match for {text!r}"


def test_is_kids_request_survives_dropped_o_in_old():
    # Real bug: this exact phrasing (a typo, or a voice-transcription
    # artifact — this app now also does real voice search via Whisper)
    # slipped through undetected because the strict "...years old" regex
    # required the literal substring "old", which "ld" doesn't contain.
    text = "I want to dress up my 2 year ld daughter in something pink and traditional"
    assert is_kids_request(text) is True


def test_age_alone_without_relation_word_does_not_trigger_kids_request():
    # "2 years" alone (no "old", no daughter/son/kid/etc.) is too weak a
    # signal on its own — e.g. "shopping here for 2 years" shouldn't be
    # treated as a kids request.
    assert is_kids_request("I've been shopping here for 2 years") is False


def test_adult_age_does_not_trigger_kids_request():
    assert is_kids_request("something for my 25 year old sister's wedding") is False


def test_kids_request_does_not_short_circuit_classify():
    # is_kids_request is layered on top in session_service, not inside
    # classify() — a kids message with no OTHER fast-path pattern in it
    # should fall through to LLM extraction like any other message, so
    # occasion/color/style still get extracted normally.
    text = "I want to dress up my 2 year old daughter in something pink and traditional"
    assert classify(text, SessionState(), []) is None


def test_cheaper_computes_budget_from_min_price(last_results):
    match = classify("can you show cheaper ones?", SessionState(), last_results)
    assert match is not None
    assert match.diff.budget_max == 2000  # floor(3000*0.9/1000)*1000 = 2000
    assert not match.show_more


def test_cheaper_with_no_prior_results_falls_through():
    assert classify("cheaper please", SessionState(), []) is None


def test_cheaper_never_goes_below_price_rounding_floor():
    cheap_results = [_product("limelight:1", 500)]
    match = classify("cheaper", SessionState(), cheap_results)
    assert match.diff.budget_max == 1000  # floor(500*0.9/1000)*1000 = 0, clamped to 1000


def test_more_formal_appends_style_descriptor():
    match = classify("show me something more formal", SessionState(), [])
    assert match is not None
    assert match.diff.style_descriptors == ["formal"]


def test_more_casual_appends_style_descriptor():
    match = classify("something more casual please", SessionState(), [])
    assert match.diff.style_descriptors == ["casual"]


def test_short_color_message_overwrites_color():
    match = classify("show me blue instead", SessionState(color_preference="red"), [])
    assert match is not None
    assert match.diff.color_preference == "blue"


def test_long_message_with_color_word_does_not_fast_path():
    # A longer, more complex request should go to full LLM extraction instead
    # of being misclassified as a simple color-swap.
    text = "something like the red one but for a wedding happening in three days"
    assert classify(text, SessionState(), []) is None


def test_different_brand_excludes_dominant_brand(last_results):
    match = classify("show me a different brand", SessionState(), last_results)
    assert match is not None
    # limelight appears twice (dominant) vs alkaram once
    assert match.diff.excluded == ["limelight"]


def test_different_brand_with_no_results_excludes_nothing():
    match = classify("different brand please", SessionState(), [])
    assert match.diff.excluded == []


def test_show_more_sets_flag_without_state_mutation():
    match = classify("show more options", SessionState(occasion="eid"), [])
    assert match is not None
    assert match.show_more is True
    assert match.diff.occasion is None
    assert match.diff.budget_max is None


def test_explicit_womenswear_refinement_is_deterministic():
    match = classify("I need women's clothing", SessionState(department="men"), [])
    assert match is not None
    assert match.diff.department == "women"


def test_compound_gender_query_falls_through_for_full_extraction():
    assert classify("women's red wedding lehenga", SessionState(), []) is None


def test_unsure_category_gets_a_formality_path():
    match = classify("not sure", SessionState(occasion="wedding"), [])
    assert match is not None
    assert match.diff.clarify is True
    assert "understated" in match.diff.assistant_reply
