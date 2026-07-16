from app.nlp.apparel_classification import classify_apparel_text, matches_classification
from app.nlp.garments import (
    extract_garment_descriptors,
    extract_primary_garment,
    extract_search_descriptors,
    ground_style_descriptors,
    matches_garment_text,
    without_garment_descriptors,
)


def test_extracts_knitted_polo_without_nested_generic_shirt():
    assert extract_search_descriptors("knitted brown polo shirts") == ["knitted", "polo"]


def test_drops_hallucinated_formal_style_and_keeps_explicit_garment():
    assert ground_style_descriptors(
        "knitted brown polos", ["formal"]
    ) == ["knitted", "polo"]


def test_keeps_formal_when_shopper_explicitly_asks_for_it():
    assert ground_style_descriptors("formal wear, no occasion", ["formal"]) == ["formal"]


def test_guide_hard_formality_exclusions_win_over_fabric_keywords():
    assert classify_apparel_text("silk t-shirt").formality == 0
    assert classify_apparel_text("plain sherwani").formality >= 2
    assert classify_apparel_text("premium denim jeans").formality == 0
    assert matches_classification("sequined t-shirt", "formal") is False


def test_shared_web_vocabulary_covers_guide_categories_without_nested_matches():
    assert extract_search_descriptors(
        "three-piece suit jeans shorts skirt formal dress shoes"
    ) == ["suit", "jeans", "shorts", "skirt", "formal", "shoes"]


def test_primary_item_is_first_product_not_the_styling_context():
    assert extract_primary_garment(
        "dark blue baggy jeans I can wear with a black shirt"
    ) == "jeans"
    assert extract_primary_garment("black shirt with blue jeans") == "shirt"


def test_common_category_typos_are_recovered_without_turning_colors_into_garments():
    assert extract_primary_garment("jeens") == "jeans"
    assert extract_primary_garment("need a jaket") == "jacket"
    assert extract_primary_garment("blue instead") is None


def test_dress_up_is_a_verb_not_the_dress_category():
    assert extract_primary_garment("dress up like a bandit for daaku day") is None


def test_category_words_are_removed_but_useful_style_words_remain():
    assert without_garment_descriptors(["baggy jeans", "knitted polo shirt"]) == [
        "baggy",
        "knitted",
    ]


def test_audience_words_are_never_kept_as_strict_styles():
    assert without_garment_descriptors(
        ["female", "women's formal", "male", "mens oversized"]
    ) == ["formal", "oversized"]


def test_provider_cannot_invent_a_garment_that_was_not_in_the_message():
    assert ground_style_descriptors("something earthy", ["kurta", "earthy"]) == [
        "earthy"
    ]


def test_store_metadata_aliases_match_the_requested_product_family():
    assert matches_garment_text("Crew Neck Knit KNITWEAR", "sweater") is True
    assert matches_garment_text("Basic Camisole Tops", "polo") is False


def test_general_product_and_attribute_vocabulary_is_grounded():
    assert extract_primary_garment("oversized cotton sweatshirts") == "sweatshirt"
    assert extract_primary_garment("women co-ord sets") == "co-ord"
    assert extract_primary_garment("wide leg trousers") == "trousers"
    assert ground_style_descriptors(
        "black slim fit leather trousers", []
    ) == ["slim fit", "leather", "trousers"]
    assert without_garment_descriptors(["stripes", "stripe", "striped"]) == [
        "striped"
    ]


def test_activewear_is_a_taxonomy_style_not_a_single_garment():
    assert extract_garment_descriptors("activewear") == []
    assert without_garment_descriptors(["activewear"]) == ["activewear"]
