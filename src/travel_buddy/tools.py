from __future__ import annotations

from typing import Annotated

from travel_buddy.models import TravelOption

WORKSHOP_USD_RATES = {
    "USD": 1.0,
    "EUR": 0.92,
    "JPY": 150.0,
    "GBP": 0.79,
}
WORKSHOP_RATE_NOTICE = "Workshop exchange rates; not for financial transactions."


def convert_currency(
    amount: Annotated[float, "Amount to convert"],
    source_currency: Annotated[str, "Three-letter source currency code"],
    target_currency: Annotated[str, "Three-letter target currency code"],
) -> dict[str, object]:
    if amount < 0:
        raise ValueError("amount cannot be negative")

    source = source_currency.strip().upper()
    target = target_currency.strip().upper()
    unsupported = sorted(code for code in {source, target} if code not in WORKSHOP_USD_RATES)
    result: dict[str, object] = {
        "input_amount": amount,
        "input_currency": source,
        "output_currency": target,
        "notice": WORKSHOP_RATE_NOTICE,
    }
    if unsupported:
        return {
            **result,
            "status": "unsupported_currency",
            "output_amount": None,
            "rate": None,
            "unsupported_codes": unsupported,
            "supported_currencies": sorted(WORKSHOP_USD_RATES),
            "error": f"Unsupported currency code(s): {', '.join(unsupported)}",
        }

    rate = WORKSHOP_USD_RATES[target] / WORKSHOP_USD_RATES[source]
    return {
        **result,
        "status": "ok",
        "output_amount": round(amount * rate, 2),
        "rate": round(rate, 6),
    }


def search_flights(
    origin: Annotated[str, "IATA origin airport code"],
    destination: Annotated[str, "IATA destination airport code"],
    departure_date: Annotated[str, "Departure date in YYYY-MM-DD format"],
) -> list[dict[str, object]]:
    route = f"{origin.upper()}-{destination.upper()}"
    return [
        TravelOption(
            provider="Contoso Air",
            summary=f"Nonstop {route} on {departure_date}",
            price_usd=420,
            metadata={"stops": 0, "duration_minutes": 345},
        ).to_dict(),
        TravelOption(
            provider="Fabrikam Airlines",
            summary=f"One-stop {route} on {departure_date}",
            price_usd=335,
            metadata={"stops": 1, "duration_minutes": 455},
        ).to_dict(),
    ]


def search_hotels(
    destination: Annotated[str, "Destination city"],
    check_in: Annotated[str, "Check-in date in YYYY-MM-DD format"],
    nights: Annotated[int, "Number of nights"],
) -> list[dict[str, object]]:
    if nights < 1:
        raise ValueError("nights must be at least 1")
    return [
        TravelOption(
            provider="Northwind Hotel",
            summary=f"Central stay in {destination} from {check_in}",
            price_usd=165 * nights,
            metadata={"nights": nights, "rating": 4.5},
        ).to_dict(),
        TravelOption(
            provider="Adventure Works Lodge",
            summary=f"Budget stay in {destination} from {check_in}",
            price_usd=110 * nights,
            metadata={"nights": nights, "rating": 4.1},
        ).to_dict(),
    ]


def estimate_trip_total(
    flight_usd: Annotated[int, "Selected flight price in USD"],
    hotel_usd: Annotated[int, "Total hotel price in USD"],
    activities_usd: Annotated[int, "Activity budget in USD"],
) -> dict[str, int]:
    values = (flight_usd, hotel_usd, activities_usd)
    if any(value < 0 for value in values):
        raise ValueError("Trip costs cannot be negative")
    return {
        "flight_usd": flight_usd,
        "hotel_usd": hotel_usd,
        "activities_usd": activities_usd,
        "total_usd": sum(values),
    }
