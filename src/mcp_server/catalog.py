from __future__ import annotations


def search_activities(destination: str, interests: list[str], budget_usd: int) -> list[dict]:
    if budget_usd < 0:
        raise ValueError("budget_usd cannot be negative")
    normalized = {interest.casefold() for interest in interests}
    catalog = [
        {"name": "Historic district walk", "interest": "history", "price_usd": 25},
        {"name": "Local food market tour", "interest": "food", "price_usd": 55},
        {"name": "Urban cycling route", "interest": "outdoors", "price_usd": 35},
    ]
    return [
        {**item, "destination": destination}
        for item in catalog
        if item["price_usd"] <= budget_usd and (not normalized or item["interest"] in normalized)
    ]


def search_lodging(
    destination: str,
    max_nightly_usd: int,
    required_amenities: list[str] | None = None,
) -> list[dict[str, object]]:
    if max_nightly_usd < 0:
        raise ValueError("max_nightly_usd cannot be negative")
    required = {amenity.casefold() for amenity in required_amenities or []}
    catalog = [
        {
            "name": "Northwind Central",
            "nightly_usd": 165,
            "amenities": ["wifi", "breakfast", "accessible"],
        },
        {
            "name": "Adventure Works Lodge",
            "nightly_usd": 110,
            "amenities": ["wifi", "kitchen"],
        },
        {
            "name": "Fabrikam Grand",
            "nightly_usd": 240,
            "amenities": ["wifi", "pool", "gym"],
        },
    ]
    return [
        {**item, "destination": destination, "notice": "Workshop inventory"}
        for item in catalog
        if item["nightly_usd"] <= max_nightly_usd
        and required.issubset({str(value).casefold() for value in item["amenities"]})
    ]


def destination_advisory(destination: str) -> dict[str, str]:
    return {
        "destination": destination,
        "advisory": (
            "Verify current entry, health, weather, and local safety guidance with "
            "authoritative sources before travel."
        ),
    }
