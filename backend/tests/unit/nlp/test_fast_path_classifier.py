"""Tests for the deterministic fast-path refinement classifier."""

import pytest

from app.nlp.fast_path_classifier import classify
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


def test_kids_request_by_age_extracts_nothing_and_clarifies():
    # Real bug: the LLM didn't reliably follow a "no kids catalog" prompt
    # instruction, extracting a nonsensical size="kids" and surfacing
    # adult womenswear as if it matched a toddler's outfit. This must be
    # a deterministic, code-level guarantee instead.
    text = "I want to dress up my 2 year old daughter in something pink and traditional"
    match = classify(text, SessionState(), [])
    assert match is not None
    assert match.diff.clarify is True
    assert match.diff.occasion is None
    assert match.diff.color_preference is None
    assert match.diff.style_descriptors == []
    assert "kids" in match.diff.assistant_reply.lower() or "adult" in match.diff.assistant_reply.lower()


def test_kids_request_by_keyword():
    for text in ["need a toddler outfit for eid", "looking for kids clothes", "something for my newborn"]:
        match = classify(text, SessionState(), [])
        assert match is not None, f"expected a kids-request match for {text!r}"
        assert match.diff.clarify is True


def test_adult_age_does_not_trigger_kids_request():
    match = classify("something for my 25 year old sister's wedding", SessionState(), [])
    # Not a kids match — either falls through to None or matches some
    # other pattern, but must never be treated as a kids request.
    if match is not None:
        assert match.diff.clarify is False or match.diff.occasion is not None


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
