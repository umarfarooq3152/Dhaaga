"""Backend-mediated search endpoint for the Chrome extension."""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from app.config import get_settings
from app.errors import ExternalServiceError
from app.llm.extension_provider import GroqExtensionProvider
from app.rate_limit import limiter
from app.schemas.extension import ExtensionSearchRequest, ExtensionSearchResponse
from app.services.extension_catalog_service import (
    CatalogUnavailableError,
    ExtensionCatalogService,
)
from app.services.extension_search_service import ExtensionSearchError, ExtensionSearchService
from app.services.product_cache_service import (
    ProductCacheService,
    close_cache_service,
    create_cache_service,
)
from app.shopify.client import ShopifyClient

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/extension", tags=["extension"])
settings = get_settings()
provider = GroqExtensionProvider(settings.groq_api_key, settings.groq_model)


async def get_extension_cache_service():
    cache_service = await create_cache_service()
    try:
        yield cache_service
    finally:
        await close_cache_service(cache_service)


async def get_extension_search_service(
    cache_service: ProductCacheService = Depends(get_extension_cache_service),
) -> ExtensionSearchService:
    catalog_service = ExtensionCatalogService(
        redis_client=cache_service.redis,
        shopify_client=ShopifyClient(timeout=5),
        max_products=settings.extension_catalog_max_products,
        ttl_seconds=settings.extension_catalog_cache_ttl_minutes * 60,
    )
    allowed_domains = {
        item.strip().lower()
        for item in settings.extension_allowed_domains.split(",")
        if item.strip()
    }
    return ExtensionSearchService(
        catalog_service=catalog_service,
        intent_provider=provider,
        allowed_domains=allowed_domains,
        rank_candidate_limit=settings.extension_rank_candidate_limit,
        result_limit=settings.extension_result_limit,
    )


@router.post("/search", response_model=ExtensionSearchResponse, response_model_by_alias=True)
@limiter.limit("10/minute")
async def search_store(
    request: Request,
    payload: ExtensionSearchRequest,
    service: ExtensionSearchService = Depends(get_extension_search_service),
) -> ExtensionSearchResponse:
    try:
        return await asyncio.wait_for(
            service.search(payload.query, payload.store_origin, payload.previous_intent),
            timeout=settings.extension_request_timeout_seconds,
        )
    except asyncio.TimeoutError as error:
        raise HTTPException(
            status_code=504,
            detail={"code": "CATALOG_TIMEOUT", "message": "The search took too long. Please try again."},
        ) from error
    except ExtensionSearchError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail={"code": error.code, "message": error.message},
        ) from error
    except CatalogUnavailableError as error:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "CATALOG_UNAVAILABLE",
                "message": "We couldn't read this store's catalog.",
            },
        ) from error
    except ExternalServiceError as error:
        logger.warning("Extension provider request failed: %s", error)
        raise HTTPException(
            status_code=502,
            detail={
                "code": "PROVIDER_UNAVAILABLE",
                "message": "Dhaaga's matching service is unavailable right now.",
            },
        ) from error
    except Exception as error:
        logger.exception("Extension search failed")
        raise HTTPException(
            status_code=500,
            detail={"code": "INTERNAL_ERROR", "message": "The search could not be completed."},
        ) from error
