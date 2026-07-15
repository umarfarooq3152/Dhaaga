"""Deterministic child-age parsing for requests and Shopify size metadata."""

import re
from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.schemas.product import Product

AgeRange = tuple[int, int]  # inclusive months

_UNIT = r"(?:m|mo|mos|month|months|y|yr|yrs|year|years)"
_RANGE_RE = re.compile(
    rf"\b(\d{{1,2}})\s*({_UNIT})?\s*(?:-|–|—|to)\s*(\d{{1,2}})\s*({_UNIT})\b",
    re.IGNORECASE,
)
_SINGLE_RE = re.compile(rf"\b(\d{{1,2}})\s*({_UNIT})\b", re.IGNORECASE)
_REQUEST_AGE_RE = re.compile(
    rf"\b(\d{{1,2}})\s*[- ]?({_UNIT})\b",
    re.IGNORECASE,
)
_AGE_OF_RE = re.compile(r"\bage\s*(?:of\s*)?(\d{1,2})\b", re.IGNORECASE)

_CHILD_RELATIONS = (
    "daughter", "son", "kid", "child", "baby", "toddler", "boy", "girl",
)


def _is_month_unit(unit: str) -> bool:
    return unit.lower().startswith("m")


def _range_in_months(start: int, end: int, unit: str) -> AgeRange | None:
    if start > end:
        return None
    if _is_month_unit(unit):
        if end > 216:
            return None
        return start, end
    if end > 17:
        return None
    # A year-labelled size covers that whole stated year. This makes both
    # 1-2Y and 2-3Y valid for a child who has just turned two, while 12Y can
    # never leak into a two-year-old request.
    return start * 12, end * 12 + 11


def extract_age_ranges(values: Iterable[str]) -> list[AgeRange]:
    """Extract explicit supported ages from product sizes/tags/text.

    Unknown/generic kids sizing deliberately yields no range. When a shopper
    supplies an exact age, products without compatible explicit metadata are
    excluded rather than guessed into the results.
    """
    ranges: set[AgeRange] = set()
    for raw_value in values:
        value = str(raw_value or "").strip()
        if not value:
            continue

        if "newborn" in value.lower():
            ranges.add((0, 3))

        remainder = value
        for match in list(_RANGE_RE.finditer(value)):
            start, start_unit, end, end_unit = match.groups()
            unit = end_unit or start_unit
            parsed = _range_in_months(int(start), int(end), unit)
            if parsed is not None:
                ranges.add(parsed)
            remainder = remainder.replace(match.group(0), " ")

        for match in _SINGLE_RE.finditer(remainder):
            amount, unit = match.groups()
            parsed = _range_in_months(int(amount), int(amount), unit)
            if parsed is not None:
                ranges.add(parsed)

        # Kids stores sometimes expose bare numeric age options ("2", "4",
        # "12") rather than "2Y". Only accept a fully numeric value, never a
        # number embedded in a title such as "2 Piece Suit".
        if re.fullmatch(r"\d{1,2}", value):
            parsed = _range_in_months(int(value), int(value), "year")
            if parsed is not None:
                ranges.add(parsed)

    return sorted(ranges)


def extract_child_age_months(text: str) -> int | None:
    """Return the exact requested child age in months when one is stated."""
    lowered = text.lower().strip()
    confirms_child = (
        "old" in lowered
        or re.search(r"\bld\b", lowered) is not None
        or any(re.search(rf"\b{word}s?\b", lowered) for word in _CHILD_RELATIONS)
    )

    match = _REQUEST_AGE_RE.search(lowered)
    if match and confirms_child:
        amount, unit = match.groups()
        amount_int = int(amount)
        months = amount_int if _is_month_unit(unit) else amount_int * 12
        if 0 <= months <= 17 * 12 + 11:
            return months

    age_match = _AGE_OF_RE.search(lowered)
    if age_match and (confirms_child or "for age" in lowered):
        years = int(age_match.group(1))
        if 0 <= years <= 17:
            return years * 12
    return None


def product_age_ranges(product: "Product") -> list[AgeRange]:
    """Return stored ranges, with a fallback for pre-change Redis entries."""
    if product.age_ranges_months:
        return [tuple(age_range) for age_range in product.age_ranges_months]
    return extract_age_ranges([
        *product.sizes,
        *product.shopify_tags,
        product.name,
        product.category or "",
    ])


def product_supports_age(product: "Product", child_age_months: int) -> bool:
    return any(start <= child_age_months <= end for start, end in product_age_ranges(product))


def products_have_compatible_ages(first: "Product", second: "Product") -> bool:
    first_ranges = product_age_ranges(first)
    second_ranges = product_age_ranges(second)
    if not first_ranges:
        return bool(second_ranges)
    return any(
        max(first_start, second_start) <= min(first_end, second_end)
        for first_start, first_end in first_ranges
        for second_start, second_end in second_ranges
    )
