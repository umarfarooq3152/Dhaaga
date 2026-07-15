from unittest.mock import AsyncMock

import pytest

from app.llm.extension_provider import GroqExtensionProvider, extract_explicit_category
from app.schemas.extension import ExtensionIntent


@pytest.mark.asyncio
async def test_parses_single_outer_json_fence():
    provider = GroqExtensionProvider("test-key", "test-model")
    provider._complete = AsyncMock(
        return_value='```json\n{"category":"t-shirt","color":"black","size":"M",'
        '"priceMax":3000,"priceMin":null,"descriptive":null}\n```'
    )
    intent = await provider.parse_intent("black t-shirt")
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
    result = await provider.parse_intent("casual shirt")
    assert result.category == "shirt"
    assert provider._complete.await_count == 2


@pytest.mark.asyncio
async def test_intent_parser_sends_previous_intent_for_refinement():
    provider = GroqExtensionProvider("test-key", "test-model")
    provider._complete = AsyncMock(
        return_value='{"category":"shirt","color":"blue","size":"M",'
        '"priceMax":3000,"priceMin":null,"descriptive":"casual"}'
    )

    previous = await provider.parse_intent("black shirt size M under 3000")
    await provider.parse_intent("blue instead", previous)

    refinement_messages = provider._complete.await_args_list[1].args[0]
    assert '"previous_intent"' in refinement_messages[1]["content"]
    assert '"new_message": "blue instead"' in refinement_messages[1]["content"]


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
