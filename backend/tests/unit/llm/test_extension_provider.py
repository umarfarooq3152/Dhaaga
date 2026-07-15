from unittest.mock import AsyncMock

import pytest

from app.llm.extension_provider import GroqExtensionProvider
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
