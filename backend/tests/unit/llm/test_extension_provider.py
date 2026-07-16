from unittest.mock import AsyncMock

import pytest

from app.llm.extension_provider import (
    GroqExtensionProvider,
    extract_explicit_category,
    extract_explicit_fit,
)
from app.schemas.extension import ExtensionIntent


@pytest.mark.asyncio
async def test_parses_single_outer_json_fence():
    provider = GroqExtensionProvider("test-key", "test-model")
    provider._complete = AsyncMock(
        return_value='```json\n{"category":"t-shirt","color":"black","size":"M",'
        '"priceMax":3000,"priceMin":null,"descriptive":null}\n```'
    )
    intent = await provider.parse_intent("ribbed black t-shirt")
    assert intent.category == "t-shirt"
    assert intent.price_max == 3000


@pytest.mark.asyncio
async def test_ranker_drops_unknown_and_duplicate_ids():
    provider = GroqExtensionProvider("test-key", "test-model")
    provider._complete = AsyncMock(
        return_value='{"rankings":['
        '{"id":"1","score":9,"reason":"Strong earthy metadata."},'
        '{"id":"1","score":8,"reason":"Duplicate."},'
        '{"id":"bad","score":10,"reason":"Unknown."}]}'
    )
    result = await provider.rank_candidates(
        "earthy", [{"id": "1", "title": "Olive shirt", "product_type": "Shirt", "tags": []}]
    )
    assert [(item.id, item.score) for item in result] == [("1", 9)]


@pytest.mark.asyncio
async def test_intent_parser_repairs_invalid_json_once():
    provider = GroqExtensionProvider("test-key", "test-model")
    provider._complete = AsyncMock(
        side_effect=[
            "not json",
            '{"category":"shirt","color":null,"size":null,"priceMax":null,'
            '"priceMin":null,"descriptive":"casual"}',
        ]
    )
    result = await provider.parse_intent("breathable shirt")
    assert result.category == "shirt"
    assert provider._complete.await_count == 2


@pytest.mark.asyncio
async def test_structured_refinement_uses_previous_intent_without_provider_latency():
    provider = GroqExtensionProvider("test-key", "test-model")
    provider._complete = AsyncMock(
        return_value='{"category":"shirt","color":"blue","size":"M",'
        '"priceMax":3000,"priceMin":null,"descriptive":"casual"}'
    )

    previous = await provider.parse_intent("black shirt size M under 3000")
    result = await provider.parse_intent("blue instead", previous)

    assert result.category == "shirt"
    assert result.color == "blue"
    assert result.size == "M"
    assert result.price_max == 3000
    provider._complete.assert_not_awaited()


@pytest.mark.asyncio
async def test_semantic_refinement_sends_previous_intent_to_provider():
    provider = GroqExtensionProvider("test-key", "test-model")
    provider._complete = AsyncMock(
        return_value='{"category":"shirt","color":"black","size":"M",'
        '"priceMax":3000,"priceMin":null,"descriptive":"lighter fabric"}'
    )
    previous = ExtensionIntent(category="shirt", color="black", size="M", priceMax=3000)

    await provider.parse_intent("make it a lighter fabric", previous)

    messages = provider._complete.await_args.args[0]
    assert '"previous_intent"' in messages[1]["content"]
    assert '"new_message": "make it a lighter fabric"' in messages[1]["content"]


@pytest.mark.asyncio
async def test_common_pink_tees_for_my_girl_query_is_local_and_grounded():
    provider = GroqExtensionProvider("test-key", "test-model")
    provider._complete = AsyncMock()

    result = await provider.parse_intent("hey show me some pink tees for my girl")

    assert result.category == "t-shirt"
    assert result.color == "pink"
    assert result.audience == "women"
    assert result.wants_kids is None
    provider._complete.assert_not_awaited()


@pytest.mark.asyncio
async def test_category_change_preserves_unrepeated_context_fields():
    provider = GroqExtensionProvider("test-key", "test-model")
    provider._complete = AsyncMock(
        return_value='{"category":"pants","color":null,"size":null,'
        '"priceMax":null,"priceMin":null,"descriptive":null}'
    )
    previous = ExtensionIntent(
        category="shirt",
        color="black",
        size="M",
        priceMax=5000,
        descriptive="smart casual",
    )

    result = await provider.parse_intent("show me pants instead", previous)

    assert result.category == "pants"
    assert result.color == "black"
    assert result.size == "M"
    assert result.price_max == 5000
    assert result.descriptive == "smart casual"


@pytest.mark.asyncio
async def test_explicit_clear_does_not_restore_removed_context_fields():
    provider = GroqExtensionProvider("test-key", "test-model")
    provider._complete = AsyncMock(
        return_value='{"category":"pants","color":null,"size":null,'
        '"priceMax":null,"priceMin":null,"descriptive":null}'
    )
    previous = ExtensionIntent(category="shirt", color="black", size="M", priceMax=5000)

    result = await provider.parse_intent("pants, any color and remove the budget", previous)

    assert result.category == "pants"
    assert result.color is None
    assert result.price_max is None
    assert result.size == "M"


@pytest.mark.asyncio
async def test_event_alias_is_normalized_deterministically():
    provider = GroqExtensionProvider("test-key", "test-model")
    provider._complete = AsyncMock(
        return_value='{"category":null,"color":null,"size":null,'
        '"priceMax":null,"priceMin":null,"descriptive":null,"occasion":null}'
    )

    result = await provider.parse_intent("something for my cousin's dholki")

    assert result.occasion == "mehndi"


@pytest.mark.asyncio
async def test_color_shade_is_normalized_deterministically():
    provider = GroqExtensionProvider("test-key", "test-model")
    provider._complete = AsyncMock(
        return_value='{"category":"shirt","color":"blue","size":null,'
        '"priceMax":null,"priceMin":null,"descriptive":null,"occasion":null}'
    )

    result = await provider.parse_intent("a navy blue shirt")

    assert result.color == "dark blue"


@pytest.mark.asyncio
async def test_model_cannot_invent_hard_color_fit_event_or_audience_constraints():
    provider = GroqExtensionProvider("test-key", "test-model")
    provider._complete = AsyncMock(
        return_value='{"category":"shirt","color":"brown","size":null,'
        '"fit":"relaxed","priceMax":null,"priceMin":null,'
        '"descriptive":"earthy weekend","occasion":"casual","audience":"women",'
        '"wantsKids":true,"childAgeMonths":60}'
    )

    result = await provider.parse_intent("an earthy weekend shirt")

    assert result.category == "shirt"
    assert result.color is None
    assert result.fit is None
    assert result.occasion is None
    assert result.audience is None
    assert result.wants_kids is None
    assert result.child_age_months is None


@pytest.mark.asyncio
async def test_grounded_previous_constraints_survive_a_plain_refinement():
    provider = GroqExtensionProvider("test-key", "test-model")
    provider._complete = AsyncMock(
        return_value='{"category":"shirt","color":"red","size":"M",'
        '"fit":"slim","priceMax":3000,"priceMin":null,'
        '"descriptive":"lighter fabric","occasion":"eid","audience":"women"}'
    )
    previous = ExtensionIntent(
        category="shirt",
        color="black",
        size="M",
        fit="regular",
        priceMax=3000,
        occasion="mehndi",
        audience="men",
    )

    result = await provider.parse_intent("make it a lighter fabric", previous)

    assert result.color == "black"
    assert result.fit == "regular"
    assert result.occasion == "mehndi"
    assert result.audience == "men"


@pytest.mark.asyncio
async def test_event_context_persists_across_extension_refinements():
    provider = GroqExtensionProvider("test-key", "test-model")
    provider._complete = AsyncMock(
        return_value='{"category":null,"color":"blue","size":null,'
        '"priceMax":null,"priceMin":null,"descriptive":null,"occasion":null}'
    )
    previous = ExtensionIntent(occasion="mehndi", category="sharara")

    result = await provider.parse_intent("blue instead", previous)

    assert result.occasion == "mehndi"
    assert result.category == "sharara"
    assert result.color == "blue"


@pytest.mark.asyncio
async def test_audience_switch_drops_old_category_size_and_keeps_neutral_context():
    provider = GroqExtensionProvider("test-key", "test-model")
    provider._complete = AsyncMock(
        return_value='{"category":"lehenga","color":"green","size":"M",'
        '"priceMax":20000,"priceMin":null,"descriptive":"embroidered",'
        '"occasion":"mehndi","audience":"men"}'
    )
    previous = ExtensionIntent(
        category="lehenga", color="green", size="M", priceMax=20000,
        descriptive="embroidered", occasion="mehndi", audience="women",
    )

    result = await provider.parse_intent("show men's instead", previous)

    assert result.audience == "men"
    assert result.category is None
    assert result.size is None
    assert result.descriptive is None
    assert result.occasion == "mehndi"
    assert result.color == "green"
    assert result.price_max == 20000


@pytest.mark.parametrize(
    ("message", "category"),
    [
        ("shes", "shoes"),
        ("formal shoes", "shoes"),
        ("find me shoes i can wear with anything", "shoes"),
        ("polos", "polo"),
        ("tank tops", "tank top"),
        ("formal pants", "pants"),
        ("sleeves", "sleeve"),
        ("belts", "belt"),
    ],
)
def test_common_catalog_categories_are_recognized_deterministically(message, category):
    assert extract_explicit_category(message) == category


@pytest.mark.asyncio
async def test_bare_new_category_drops_copied_old_topic_constraints():
    provider = GroqExtensionProvider("test-key", "test-model")
    provider._complete = AsyncMock(
        return_value='{"category":"tank top","color":"black","size":null,'
        '"priceMax":null,"priceMin":null,"descriptive":"formal",'
        '"occasion":null,"audience":null,"wantsKids":true,"childAgeMonths":60}'
    )
    previous = ExtensionIntent(
        category="pants",
        color="black",
        descriptive="formal",
        wantsKids=True,
        childAgeMonths=60,
    )

    result = await provider.parse_intent("tank tops", previous)

    assert result.category == "tank top"
    assert result.color is None
    assert result.descriptive is None
    assert result.wants_kids is None
    assert result.child_age_months is None


@pytest.mark.asyncio
async def test_new_topic_keeps_constraints_explicitly_repeated_in_new_message():
    provider = GroqExtensionProvider("test-key", "test-model")
    provider._complete = AsyncMock(
        return_value='{"category":"pants","color":"black","size":null,'
        '"priceMax":null,"priceMin":null,"descriptive":"formal"}'
    )
    previous = ExtensionIntent(category="shirt", color="black", descriptive="formal")

    result = await provider.parse_intent("black formal pants", previous)

    assert result.category == "pants"
    assert result.color == "black"
    assert result.descriptive == "formal"


@pytest.mark.asyncio
async def test_kids_age_is_extracted_even_when_model_misses_it():
    provider = GroqExtensionProvider("test-key", "test-model")
    provider._complete = AsyncMock(
        return_value='{"category":"pants","color":null,"size":null,'
        '"priceMax":null,"priceMin":null,"descriptive":"formal"}'
    )

    result = await provider.parse_intent("formal pants for my 5 year old kid")

    assert result.category == "pants"
    assert result.wants_kids is True
    assert result.child_age_months == 60
    assert result.size is None


@pytest.mark.asyncio
async def test_baggy_is_a_fit_and_never_a_size():
    provider = GroqExtensionProvider("test-key", "test-model")
    provider._complete = AsyncMock(
        return_value='{"category":"jeans","color":"black","size":"baggy",'
        '"priceMax":null,"priceMin":null,"descriptive":"crapper"}'
    )
    previous = ExtensionIntent(category="jeans")

    result = await provider.parse_intent(
        "I want to buy some baggy jeans, a black colored crapper.",
        previous,
    )

    assert extract_explicit_fit("baggy jeans") == "baggy"
    assert result.category == "jeans"
    assert result.color == "black"
    assert result.fit == "baggy"
    assert result.size is None
    assert result.descriptive is None


@pytest.mark.asyncio
async def test_standalone_juniors_clothes_starts_a_clean_kids_topic():
    provider = GroqExtensionProvider("test-key", "test-model")
    provider._complete = AsyncMock(
        return_value='{"category":"sweater","color":"black","size":null,'
        '"priceMax":null,"priceMin":null,"descriptive":"winter",'
        '"wantsKids":null,"childAgeMonths":null}'
    )
    previous = ExtensionIntent(category="sweater", color="black", descriptive="winter")

    result = await provider.parse_intent("juniors cloths", previous)

    assert result.category is None
    assert result.color is None
    assert result.descriptive is None
    assert result.wants_kids is True


@pytest.mark.asyncio
async def test_multiple_alternative_colors_are_preserved_as_or_not_and():
    provider = GroqExtensionProvider("test-key", "test-model")
    provider._complete = AsyncMock(
        return_value='{"category":"polo","color":"brown","size":null,'
        '"priceMax":null,"priceMin":null,"descriptive":"knitted"}'
    )

    result = await provider.parse_intent("some knitted polos, brown or red")

    assert result.color == "brown or red"


@pytest.mark.asyncio
async def test_adult_garment_after_juniors_topic_does_not_keep_kids_filter():
    provider = GroqExtensionProvider("test-key", "test-model")
    provider._complete = AsyncMock(
        return_value='{"category":"jeans","color":"dark blue","size":null,'
        '"priceMax":null,"priceMin":null,"descriptive":"baggy",'
        '"wantsKids":true,"childAgeMonths":null}'
    )
    previous = ExtensionIntent(wantsKids=True)

    result = await provider.parse_intent(
        "dark blue baggy jeans I can wear with a black shirt", previous
    )

    assert result.category == "jeans"
    assert result.color == "dark blue"
    assert result.wants_kids is None


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("jeens", "jeans"),
        ("poloss", "polo"),
        ("need a jaket", "jacket"),
        ("show me hoodi", "hoodie"),
        ("black shirt with blue jeans", "shirt"),
        ("blue jeans with a black shirt", "jeans"),
    ],
)
def test_conversational_category_corpus_handles_typos_and_primary_item_order(message, expected):
    assert extract_explicit_category(message) == expected


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("button-down office shirt", "shirt"),
        ("silk blouse", "blouse"),
        ("camisole", "tank top"),
        ("sequined crop top", "crop top"),
        ("peplum top", "peplum top"),
        ("western tunic", "tunic"),
        ("lawn kurta", "kurta"),
        ("short kurti", "kurti"),
        ("shalwar kameez", "shalwar kameez"),
        ("three-piece chiffon suit", "suit"),
        ("shirt dress", "shirt dress"),
        ("wrap dress", "wrap dress"),
        ("cocktail dress", "cocktail dress"),
        ("slip dress", "slip dress"),
        ("maxi dress", "maxi"),
        ("floor-length gown", "gown"),
        ("palazzo", "palazzo"),
        ("cigarette pants", "cigarette pants"),
        ("gharara", "gharara"),
        ("sharara", "sharara"),
        ("leggings", "leggings"),
        ("tailored blazer", "blazer"),
        ("embroidered waistcoat", "waistcoat"),
        ("chiffon shrug", "shrug"),
        ("event cape", "cape"),
        ("knit cardigan", "cardigan"),
        ("sherwani", "sherwani"),
        ("achkan", "achkan"),
        ("formal dress shoes", "shoes"),
        ("sports bra", "sports bra"),
        ("track pants", "joggers"),
        ("windbreaker", "windbreaker"),
        ("swimwear", "swimwear"),
        ("lehenga", "lehenga"),
        ("pishwas", "pishwas"),
        ("saree", "saree"),
        ("abaya", "abaya"),
        ("prince coat", "prince coat"),
    ],
)
def test_complete_guide_category_vocabulary(message, expected):
    assert extract_explicit_category(message) == expected


def test_color_refinement_is_never_fuzzy_corrected_into_a_garment():
    assert extract_explicit_category("blue instead") is None


@pytest.mark.asyncio
async def test_model_adjective_mistaken_for_size_is_recovered_as_style():
    provider = GroqExtensionProvider("test-key", "test-model")
    provider._complete = AsyncMock(
        return_value='{"category":"shirt","color":null,"size":"formal",'
        '"priceMax":null,"priceMin":null,"descriptive":null}'
    )

    result = await provider.parse_intent("a formal shirt")

    assert result.size is None
    assert result.descriptive == "formal"
