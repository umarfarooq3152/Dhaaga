import pytest

from app.nlp.apparel_classification import (
    BRIDAL,
    CASUAL,
    FORMAL,
    PARTY,
    SEMI_FORMAL,
    classify_apparel_text,
    extract_classification_request,
    matches_classification,
)


@pytest.mark.parametrize(
    ("label", "minimum", "maximum"),
    [
        # Western shirts and tops
        ("plain cotton button-down office shirt", FORMAL, FORMAL),
        ("flannel button-down shirt", CASUAL, CASUAL),
        ("knitted polo shirt", CASUAL, SEMI_FORMAL),
        ("premium silk crew neck t-shirt", CASUAL, CASUAL),
        ("structured silk blouse", FORMAL, FORMAL),
        ("cotton casual print blouse", CASUAL, SEMI_FORMAL),
        ("ribbed tank top camisole", CASUAL, CASUAL),
        ("sequined crop top", PARTY, PARTY),
        ("structured peplum top", FORMAL, PARTY),
        ("plain western tunic", CASUAL, SEMI_FORMAL),
        # Eastern tops
        ("plain lawn cotton kurta", CASUAL, CASUAL),
        ("lawn kurta with light embroidery", SEMI_FORMAL, SEMI_FORMAL),
        ("chiffon silk embroidered kurta", FORMAL, FORMAL),
        ("heavily embellished mirror work kurta", PARTY, PARTY),
        ("angrakha kurta", FORMAL, PARTY),
        ("short cotton kurti", CASUAL, SEMI_FORMAL),
        ("digital print lawn kurta", SEMI_FORMAL, SEMI_FORMAL),
        ("digital print chiffon kurta", FORMAL, FORMAL),
        ("plain khaddar kurta", SEMI_FORMAL, SEMI_FORMAL),
        # Eastern suits and sets
        ("unstitched lawn 2-piece suit", CASUAL, CASUAL),
        ("unstitched lawn 3-piece suit with dupatta", SEMI_FORMAL, SEMI_FORMAL),
        ("stitched lawn suit embroidered", SEMI_FORMAL, SEMI_FORMAL),
        ("chiffon silk 3-piece suit embroidered", FORMAL, FORMAL),
        ("organza net 3-piece heavily embellished", PARTY, PARTY),
        ("velvet 3-piece winter formal", FORMAL, PARTY),
        ("bridal couture 3-piece dupatta zari dabka", BRIDAL, BRIDAL),
        # Dresses
        ("cotton jersey casual day dress", CASUAL, CASUAL),
        ("cotton shirt dress", CASUAL, SEMI_FORMAL),
        ("silk satin wrap dress", FORMAL, FORMAL),
        ("cocktail dress", PARTY, PARTY),
        ("structured floor-length gown", FORMAL, PARTY),
        ("cotton casual maxi dress", CASUAL, CASUAL),
        ("structured embroidered maxi dress", FORMAL, PARTY),
        ("cotton slip dress", CASUAL, CASUAL),
        ("satin slip dress", PARTY, PARTY),
        # Bottoms
        ("premium dark wash jeans", CASUAL, CASUAL),
        ("formal fitted leggings", CASUAL, CASUAL),
        ("tailored linen trousers", SEMI_FORMAL, FORMAL),
        ("dress pants suiting trousers", FORMAL, FORMAL),
        ("plain palazzo", CASUAL, SEMI_FORMAL),
        ("printed silk palazzo", FORMAL, PARTY),
        ("cigarette pants", SEMI_FORMAL, FORMAL),
        ("plain cotton shalwar", CASUAL, CASUAL),
        ("embroidered chiffon shalwar", FORMAL, FORMAL),
        ("gharara", PARTY, BRIDAL),
        ("sharara", PARTY, BRIDAL),
        ("leggings tights", CASUAL, CASUAL),
        ("plain cotton joggers", CASUAL, CASUAL),
        ("shorts", CASUAL, CASUAL),
        # Outerwear
        ("denim jacket", CASUAL, CASUAL),
        ("plain tailored blazer", FORMAL, FORMAL),
        ("eastern embroidered waistcoat", FORMAL, PARTY),
        ("plain jersey shrug", CASUAL, CASUAL),
        ("chiffon embellished shrug", FORMAL, FORMAL),
        ("embellished event wear cape", FORMAL, PARTY),
        ("knit cardigan", CASUAL, CASUAL),
        ("sherwani", PARTY, BRIDAL),
        ("achkan", FORMAL, PARTY),
        # Footwear
        ("premium leather sneakers", CASUAL, CASUAL),
        ("plain sandals flats", CASUAL, CASUAL),
        ("plain khussa", CASUAL, SEMI_FORMAL),
        ("embroidered khussa", FORMAL, PARTY),
        ("plain heels", SEMI_FORMAL, FORMAL),
        ("embellished jeweled heels", PARTY, BRIDAL),
        ("men's formal dress shoes", FORMAL, FORMAL),
        ("loafers", CASUAL, SEMI_FORMAL),
    ],
)
def test_complete_guide_formality_mapping(label, minimum, maximum):
    tier = classify_apparel_text(label).formality
    assert minimum <= tier <= maximum, (label, tier)


@pytest.mark.parametrize(
    "label",
    [
        "activewear training set",
        "dri-fit gym t-shirt",
        "moisture-wicking compression leggings",
        "performance bike shorts",
        "track pants training",
        "high-waist stretch leggings",
        "performance fabric joggers",
        "sports bra",
        "sports hijab",
        "yoga pants 4-way stretch",
        "running shoes trainers",
        "windbreaker",
    ],
)
def test_complete_activewear_mapping(label):
    assert classify_apparel_text(label).activewear is True


def test_plain_cotton_gym_items_and_swimwear_are_not_misclassified_as_activewear():
    assert classify_apparel_text("plain cotton t-shirt").activewear is False
    assert classify_apparel_text("plain cotton joggers").activewear is False
    assert classify_apparel_text("swimwear swimsuit").activewear is False


@pytest.mark.parametrize(
    ("label", "family"),
    [
        ("kurta", "eastern"),
        ("kameez", "eastern"),
        ("shalwar", "eastern"),
        ("gharara", "eastern"),
        ("sharara", "eastern"),
        ("dupatta", "eastern"),
        ("sherwani", "eastern"),
        ("achkan", "eastern"),
        ("khussa", "eastern"),
        ("waistcoat", "eastern"),
        ("button-down shirt", "western"),
        ("t-shirt", "western"),
        ("jeans", "western"),
        ("dress", "western"),
        ("trousers", "western"),
        ("blazer", "western"),
        ("gown", "western"),
        ("heels", "western"),
        ("sneakers", "western"),
        ("palazzo", "fusion"),
        ("cigarette pants", "fusion"),
        ("kurti", "fusion"),
        ("cape", "fusion"),
        ("peplum top", "fusion"),
        ("jumpsuit", "fusion"),
        ("tunic", "fusion"),
    ],
)
def test_complete_eastern_western_fusion_mapping(label, family):
    assert classify_apparel_text(label).tradition == family


def test_hard_exclusions_override_conflicting_marketing_words():
    assert matches_classification("luxury silk formal t-shirt", "formal") is False
    assert matches_classification("premium formal jeans", "formal") is False
    assert matches_classification("formal fitted denim jacket", "formal") is False
    assert matches_classification("formal flannel button-down shirt", "formal") is False
    assert matches_classification("formal knit cardigan", "formal") is False
    assert matches_classification("formal leather sneakers", "formal") is False
    assert matches_classification("simple casual sherwani", "casual") is False
    assert matches_classification("simple casual gharara", "casual") is False
    assert matches_classification("simple casual sharara", "casual") is False
    assert classify_apparel_text("plain velvet dress").formality >= FORMAL
    assert classify_apparel_text("plain net dress").formality >= FORMAL
    assert matches_classification("casual velvet dress", "casual") is False
    assert matches_classification("casual heavily embellished kurta", "casual") is False


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("crisp woven button-down shirt", FORMAL),
        ("lawn kurta with embellishment", SEMI_FORMAL),
        ("organza kurta with gota handwork", PARTY),
        ("raw silk kameez with mukaish and kamdani", PARTY),
        ("satin slip dress", PARTY),
        ("silk embellished palazzo", FORMAL),
    ],
)
def test_fabric_construction_and_regional_work_matrix(label, expected):
    assert classify_apparel_text(label).formality == expected


def test_negated_work_is_not_counted_as_embellishment_evidence():
    assert classify_apparel_text("plain lawn kurta with no embroidery").formality == CASUAL
    assert classify_apparel_text("silk kurta without embellishment").formality == FORMAL


@pytest.mark.parametrize(
    ("query", "formality", "family", "activewear"),
    [
        ("semi formal eastern wear", "semi-formal", "eastern", False),
        ("western formal clothes", "formal", "western", False),
        ("fusion party wear", "party", "fusion", False),
        ("bridal eastern outfit", "bridal", "eastern", False),
        ("gym clothes", None, None, True),
        ("sportswear", None, None, True),
    ],
)
def test_complete_request_mapping(query, formality, family, activewear):
    request = extract_classification_request(query)
    assert request.formality == formality
    assert request.tradition == family
    assert request.activewear is activewear
