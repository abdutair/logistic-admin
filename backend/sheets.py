import os
import json
import re
from datetime import datetime, timezone
from typing import Any

import httpx


WEBHOOK_URL = os.getenv("GOOGLE_SHEETS_WEBHOOK_URL", "")


def first_present(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, "", [], {}):
            return value
    return ""


def short_place_name(value: Any) -> str:
    value = str(value or "").strip()
    if not value:
        return ""

    if '"' in value:
        parts = value.split('"')
        if len(parts) >= 3 and parts[1].strip():
            return parts[1].strip().title()

    value = value.split("-", 1)[0].strip()
    words = value.split()
    if len(words) > 1:
        return words[-1].strip('"').title()
    return value.strip('"').title()


def short_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d / %H:%M")


def vehicle_numbers_parts(data: dict[str, Any]) -> list[str]:
    direct = [
        clean
        for clean in [
            str(data.get("truck_registration_number") or "").strip(),
            str(data.get("trailer_registration_number") or "").strip(),
        ]
        if clean
    ]
    if direct:
        return direct

    value = first_present(data, "vehicle_registration_numbers_text", "vehicle_registration_numbers")
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]

    value = str(value or "").strip()
    if not value:
        return []

    kg_numbers = re.findall(r"\d{2}KG\d{3}[A-Z]{2,3}", value, flags=re.IGNORECASE)
    if len(kg_numbers) > 1:
        return [number.upper() for number in kg_numbers]

    ru_pair = re.fullmatch(r"([A-Z]{2}\d{4})([A-Z]{2}\d{3})", value, flags=re.IGNORECASE)
    if ru_pair:
        return [ru_pair.group(1).upper(), ru_pair.group(2).upper()]

    parts = [part.strip() for part in re.split(r"[\n,;/\s-]+", value) if part.strip()]
    return parts if len(parts) > 1 else [value]


def vehicle_numbers_compact(data: dict[str, Any]) -> str:
    return "-".join(vehicle_numbers_parts(data))


async def send_to_sheets(data: dict[str, Any], user_name: str, filename: str) -> dict[str, Any]:
    if not WEBHOOK_URL:
        return {"success": False, "error": "GOOGLE_SHEETS_WEBHOOK_URL не задан"}
    if "ТВОЙ_ID" in WEBHOOK_URL or "YOUR_SCRIPT_ID" in WEBHOOK_URL:
        return {"success": False, "error": "В GOOGLE_SHEETS_WEBHOOK_URL указан шаблон, нужен реальный Apps Script URL"}

    vehicle_numbers = vehicle_numbers_compact(data)
    arrival_checkpoint = data.get("arrival_checkpoint")
    customs_office = data.get("customs_office")
    arrival_checkpoint_short = short_place_name(arrival_checkpoint)
    customs_office_short = short_place_name(customs_office)
    route = "-".join(part for part in [arrival_checkpoint_short, customs_office_short] if part)
    if not route:
        route = first_present(data, "route")

    notes = first_present(data, "notes", "invoice_number")
    client_name = str(data.get("client") or "").strip()

    payload = {
        "timestamp": data.get("timestamp") or short_timestamp(),
        "user": user_name,
        "client": client_name,
        "status": data.get("status") or "Подан",
        "filename": "",
        "registration_number": data.get("registration_number"),
        "arrival_checkpoint": arrival_checkpoint,
        "arrival_checkpoint_short": arrival_checkpoint_short,
        "arrival_point": arrival_checkpoint,
        "arrival_customs_point": arrival_checkpoint,
        "customs_office": customs_office,
        "customs_office_short": customs_office_short,
        "departure_arrival_customs_office": customs_office,
        "customs_office_departure_destination": customs_office,
        "vehicle_registration_numbers": vehicle_numbers,
        "vehicle_registration_numbers_text": vehicle_numbers,
        "vehicle_numbers": vehicle_numbers,
        "vehicle_numbers_compact": vehicle_numbers,
        "vehicle_numbers_column": vehicle_numbers,
        "transport_vehicle_numbers": vehicle_numbers,
        "ts_numbers": vehicle_numbers,
        "car_numbers": vehicle_numbers,
        "vehicle": vehicle_numbers,
        "transport": vehicle_numbers,
        "ТС": vehicle_numbers,
        "Номера ТС": vehicle_numbers,
        "vehicle_number": vehicle_numbers,
        "transport_number": vehicle_numbers,
        "transport_registration_number": vehicle_numbers,
        "truck_registration_number": data.get("truck_registration_number"),
        "trailer_registration_number": data.get("trailer_registration_number"),
        "sender": data.get("sender"),
        "receiver": data.get("receiver"),
        "first_good_hs_code_and_name": data.get("first_good_hs_code_and_name"),
        "first_good_gross_weight_kg": data.get("first_good_gross_weight_kg"),
        "first_good_unit": data.get("first_good_unit"),
        "first_good_quantity": data.get("first_good_quantity"),
        "first_good_currency_and_value": data.get("first_good_currency_and_value"),
        "first_good_country": data.get("first_good_country"),
        "first_good_shipping_document": data.get("first_good_shipping_document"),
        "total_goods_count": data.get("total_goods_count") or data.get("goods_count"),
        "total_net_weight_kg": data.get("total_net_weight_kg"),
        "total_gross_weight_kg": data.get("total_gross_weight_kg"),
        "total_cargo_places": data.get("total_cargo_places"),
        "gross_weight_kg": first_present(data, "total_gross_weight_kg", "first_good_gross_weight_kg", "weight_kg"),
        "net_weight_kg": data.get("total_net_weight_kg"),
        "cargo_places": data.get("total_cargo_places"),
        "cargo_places_total": data.get("total_cargo_places"),
        "invoice_number": data.get("invoice_number"),
        "total_value": data.get("total_value"),
        "doc_number": first_present(data, "doc_number", "registration_number"),
        "doc_date": first_present(data, "doc_date", "transport_doc_date"),
        "sender_address": data.get("sender_address"),
        "receiver_address": data.get("receiver_address"),
        "cargo_description": first_present(data, "cargo_description", "first_good_hs_code_and_name", "first_good_name"),
        "weight_kg": first_present(data, "weight_kg", "total_gross_weight_kg", "first_good_gross_weight_kg"),
        "quantity": first_present(data, "quantity", "total_goods_count", "goods_count", "first_good_quantity"),
        "route": route,
        "carrier": first_present(data, "carrier", "carrier_id", "driver", "driver_id"),
        "notes": notes,
        "all_data": json.dumps(data, ensure_ascii=False),
    }
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            response = await client.post(WEBHOOK_URL, json=payload)
    except httpx.HTTPError as exc:
        return {"success": False, "error": f"Ошибка запроса к Google Sheets: {exc}"}

    if response.status_code != 200:
        return {
            "success": False,
            "error": f"Google Apps Script вернул HTTP {response.status_code}: {response.text[:300]}",
        }
    return {"success": True}
