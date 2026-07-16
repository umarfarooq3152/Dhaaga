from app.schemas.session import IntentExtractionResult


def test_hard_constraints_win_over_duplicate_soft_preferences():
    intent = IntentExtractionResult(
        assistant_reply="ok",
        hard_constraints=["department", "occasion", "department"],
        soft_preferences=["occasion", "color_preference", "color_preference"],
    )

    assert intent.hard_constraints == ["department", "occasion"]
    assert intent.soft_preferences == ["color_preference"]


def test_legacy_cached_intent_remains_readable_with_v2_defaults():
    intent = IntentExtractionResult.model_validate({
        "occasion": "mehndi",
        "style_descriptors": ["embroidered"],
        "assistant_reply": "ok",
    })

    assert intent.operation == "refine"
    assert intent.semantic_query == ""
    assert intent.hard_constraints == []
    assert intent.confidence.overall == 0.5


def test_provider_constraint_labels_are_canonicalized_without_losing_intent():
    intent = IntentExtractionResult(
        occasion="mehndi",
        style_descriptors=["bright"],
        hard_constraints=["audience", "occasion"],
        soft_preferences=["color", "bright", "style"],
        assistant_reply="",
    )

    assert intent.hard_constraints == ["department", "occasion"]
    assert intent.soft_preferences == ["color_preference", "style_descriptors"]


def test_generic_clothing_and_bright_are_normalized_as_semantic_preferences():
    intent = IntentExtractionResult(
        occasion="mehndi",
        category="clothing",
        color_preference="bright",
        hard_constraints=["occasion", "department"],
        soft_preferences=["color_preference"],
        assistant_reply="",
    )

    assert intent.category is None
    assert intent.color_preference is None
    assert intent.style_descriptors == ["bright"]
    assert intent.hard_constraints == ["occasion", "department"]
    assert intent.soft_preferences == ["style_descriptors"]
