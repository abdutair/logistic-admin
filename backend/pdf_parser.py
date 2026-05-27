import re
from typing import Any

import pdfplumber


def clean_value(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def find_field(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            if len(match.groups()) > 1:
                return " - ".join(clean_value(group) for group in match.groups() if group)
            return clean_value(match.group(1))
    return ""


def find_between(text: str, start: str, end_markers: list[str]) -> str:
    match = re.search(rf"{re.escape(start)}\s*\n(.+?)(?=\n(?:{'|'.join(map(re.escape, end_markers))})\b)", text, re.DOTALL)
    return clean_value(match.group(1)) if match else ""


def split_name_and_id(value: str, id_label: str = "") -> tuple[str, str]:
    value = clean_value(value)
    if not value:
        return "", ""
    if id_label:
        pattern = rf"(.+?)\s*/\s*{re.escape(id_label)}:\s*([A-ZА-Яа-я0-9\-\/]+)"
        match = re.search(pattern, value, re.IGNORECASE)
        if match:
            return clean_value(match.group(1)), clean_value(match.group(2))
    if " - " in value:
        name, identifier = value.rsplit(" - ", 1)
        return clean_value(name), clean_value(identifier)
    return value, ""


def normalize_decimal(value: str) -> str:
    value = clean_value(value).replace(" ", "")
    parts = value.split()
    if len(parts) > 1 and all(re.fullmatch(r"[\d.]+", part) for part in parts):
        return "".join(parts)
    return value


def strip_trailing_zeroes(value: Any) -> str:
    value = clean_value(value)
    if re.fullmatch(r"\d+\.0+", value):
        return value.split(".", 1)[0]
    if re.fullmatch(r"\d+\.\d+", value):
        return value.rstrip("0").rstrip(".")
    return value


def clean_goods_name(value: Any) -> str:
    value = clean_value(value)
    value = re.sub(r"\b(?:Сведения\s+о\s+товаре|ения\s+о\s+товаре|ения\s+о)\b", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"товар[еа]?", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"това(?=[А-ЯA-Z])", " ", value, flags=re.IGNORECASE)
    value = value.replace("енСБиОяР НоА", "СБОРНАЯ")
    value = value.replace("енСБиОяРНоА", "СБОРНАЯ")
    value = value.replace("енияС оТР тОоИвТаЕЛрЬеНЫХ", "СТРОИТЕЛЬНЫХ")
    value = value.replace("енияС оТР тОоИвТаЕЛЬеНЫХ", "СТРОИТЕЛЬНЫХ")
    value = value.replace("СвТаАрЛеЬНАЯ", "СТАЛЬНАЯ")
    value = value.replace("СвТаАрЛеЬНОЙ", "СТАЛЬНОЙ")
    value = re.sub(r"\bтЯо\b", " ", value)
    value = value.replace("ЗрОе", "ЗО")
    value = value.replace("СтТоАвЛаЬрНеАЯ", "СТАЛЬНАЯ")
    value = value.replace("СтТоАвЛаЬрНеАя", "СТАЛЬНАЯ")
    value = value.replace("СтТоАвЛаЬрНОеЙ", "СТАЛЬНОЙ")
    value = value.replace("СтТоАвЛаЬрНОЙ", "СТАЛЬНОЙ")
    value = re.sub(r"Ст\s*То\s*Ав\s*Ла\s*Ьр\s*Н[Оо]е?Й", "СТАЛЬНОЙ", value)
    value = value.replace("тоЗАвЗаЕрМеЛЕНИЯ", "ЗАЗЕМЛЕНИЯ")
    value = value.replace("тоЗАвЗаЕрМеЛения", "ЗАЗЕМЛЕНИЯ")
    value = re.sub(r"\bто(?=[А-ЯA-Z])", "", value)
    value = re.sub(r"\s+", " ", value).strip()

    dimensions_match = re.match(r"^((?:\d+(?:[.,]\d+)?М\s*)+)\s+(.+)$", value, re.IGNORECASE)
    if dimensions_match:
        dimensions = clean_value(dimensions_match.group(1)).upper()
        name = clean_value(dimensions_match.group(2)).upper()
        return f"{name} {dimensions}".strip()

    return value


def split_vehicle_number(value: Any) -> list[str]:
    value = clean_value(value).upper()
    if not value:
        return []

    kg_numbers = re.findall(r"\d{2}KG\d{3}[A-Z]{2,3}", value)
    if len(kg_numbers) > 1:
        return kg_numbers

    ru_pair = re.fullmatch(r"([A-Z]{2}\d{4})([A-Z]{2}\d{3})", value)
    if ru_pair:
        return [ru_pair.group(1), ru_pair.group(2)]

    parts = [part for part in re.split(r"[\n,;/\s-]+", value) if part]
    return parts if len(parts) > 1 else [value]


def compact_vehicle_numbers(numbers: list[str]) -> str:
    compacted: list[str] = []
    for number in numbers:
        for part in split_vehicle_number(number):
            if part and part not in compacted:
                compacted.append(part)
    return "-".join(compacted)


def extract_vehicle_numbers_from_text(text: str) -> list[str]:
    numbers: list[str] = []
    patterns = [
        r"\d{2}KG\d{3}[A-Z]{2,3}",
        r"[A-Z]{2}\d{4}[A-Z]{2}\d{3}",
    ]
    for pattern in patterns:
        for match in re.findall(pattern, text, flags=re.IGNORECASE):
            for part in split_vehicle_number(match):
                if part not in numbers:
                    numbers.append(part)
    return numbers


def parse_tables(tables: list[list[list[str | None]]]) -> dict[str, Any]:
    result: dict[str, Any] = {"vehicles": [], "goods": []}

    for table in tables:
        if not table:
            continue

        header = [clean_value(cell) for cell in table[0]]
        header_text = " ".join(header).lower()

        if "страна регистрации" in header_text and "номер регистрации" in header_text:
            for row in table[1:]:
                if len(row) >= 3:
                    result["vehicles"].append({
                        "registration_country": clean_value(row[0]),
                        "registration_number": clean_value(row[1]),
                        "transport_type": clean_value(row[2]),
                    })

        if "документы(грузосопроводительные)" in header_text:
            for row in table[1:]:
                if len(row) < 8:
                    continue
                item_number = find_field(clean_value(row[0]), [r"^(\d+)"])
                code_and_name = clean_goods_name(row[1])
                hs_code, cargo_name = split_code_and_name(code_and_name)
                cargo_name = clean_goods_name(cargo_name)
                doc_type, doc_number, doc_date = split_goods_document(clean_value(row[7]))
                result["goods"].append({
                    "item_number": item_number,
                    "hs_code": hs_code,
                    "name": cargo_name,
                    "gross_weight_kg": strip_trailing_zeroes(normalize_numeric_cell(row[2])),
                    "unit": clean_value(row[3]),
                    "quantity": clean_value(row[4]),
                    "currency": clean_value(row[5]).split(" / ")[0] if row[5] else "",
                    "value": strip_trailing_zeroes(clean_value(row[5]).split(" / ")[1]) if row[5] and " / " in clean_value(row[5]) else "",
                    "country": clean_value(row[6]),
                    "document_type": doc_type,
                    "document_number": doc_number,
                    "document_date": doc_date,
                })

    return result


def normalize_numeric_cell(value: Any) -> str:
    value = "" if value is None else str(value).strip()
    pieces = [piece.strip() for piece in value.splitlines() if piece.strip()]
    if len(pieces) > 1 and all(re.fullmatch(r"[\d.]+", piece) for piece in pieces):
        return "".join(pieces)
    return clean_value(value)


def split_code_and_name(value: str) -> tuple[str, str]:
    if " / " in value:
        code, name = value.split(" / ", 1)
        return clean_value(code), clean_value(name)
    match = re.match(r"(\d{6,})\s+(.+)", value)
    if match:
        return clean_value(match.group(1)), clean_value(match.group(2))
    return "", clean_value(value)


def split_goods_document(value: str) -> tuple[str, str, str]:
    parts = [clean_value(part) for part in value.split("/") if clean_value(part)]
    return (
        parts[0] if len(parts) > 0 else "",
        parts[1] if len(parts) > 1 else "",
        parts[2] if len(parts) > 2 else "",
    )


def parse_preliminary_information(text: str, tables: list[list[list[str | None]]]) -> dict[str, Any]:
    applicant, applicant_pin = split_name_and_id(
        find_field(text, [r"Лицо,\s*подающее\s*ПИ\s+(.+?)(?=\nЦель представления ПИ)"]),
        "Пин",
    )
    carrier, carrier_id = split_name_and_id(find_field(text, [r"Информация о перевозчике\s+([^\n]+)"]))
    driver, driver_id = split_name_and_id(find_field(text, [r"Информация о водителе\s+([^\n]+)"]))
    checkpoint = find_field(text, [r"Наименование пункта пропуска прибытия\s+([^\n]+)"])
    customs_office = find_field(text, [r"Таможенный орган убытия/назначения\s+([^\n]+)"])
    transport_tables = parse_tables(tables)

    goods = transport_tables["goods"]
    first_good = goods[0] if goods else {}
    sender = find_between(text, "Отправитель", ["Получатель"])
    receiver = find_between(text, "Получатель", ["Регистрационный номер", "Сведения о товаре"])
    sender_name, sender_id = split_name_and_id(sender)
    receiver_name, receiver_id = split_name_and_id(receiver)
    vehicles = transport_tables["vehicles"]
    vehicle_registration_numbers = [
        vehicle["registration_number"]
        for vehicle in vehicles
        if vehicle.get("registration_number")
    ]
    if not vehicle_registration_numbers:
        vehicle_registration_numbers = extract_vehicle_numbers_from_text(text)
    vehicle_registration_numbers_compact = compact_vehicle_numbers(vehicle_registration_numbers)
    first_good_document = " / ".join(
        part
        for part in [
            first_good.get("document_type", ""),
            first_good.get("document_number", ""),
            first_good.get("document_date", ""),
        ]
        if part
    )
    first_good_currency_and_value = " / ".join(
        part
        for part in [
            first_good.get("currency", ""),
            first_good.get("value", ""),
        ]
        if part
    )

    result: dict[str, Any] = {
        "document_type": "Предварительное информирование",
        "registration_number": find_field(text, [r"Регистрационный номер\s+([^\n]+)"]),
        "doc_number": find_field(text, [r"Регистрационный номер\s+([^\n]+)"]),
        "applicant": applicant,
        "applicant_pin": applicant_pin,
        "pi_purpose": find_field(text, [r"Цель представления ПИ\s+(.+?)(?=\nНаименование пункта пропуска прибытия)"]),
        "arrival_checkpoint": checkpoint,
        "arrival_checkpoint_code": find_field(checkpoint, [r"-\s*([A-ZА-Я0-9]+)$"]),
        "arrival_datetime": find_field(text, [r"Дата и время прибытия\s+(\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2})"]),
        "origin_country": find_field(text, [r"Страна отправления товарной партии:\s*(.+?)(?=\nСтрана назначения товарной партии:)"]),
        "destination_country": find_field(text, [r"Страна назначения товарной партии:\s*(.+?)(?=\nТаможенный орган убытия/назначения)"]),
        "customs_office": customs_office,
        "customs_office_code": find_field(customs_office, [r"-\s*([A-ZА-Я0-9]+)$"]),
        "intermediate_country": find_field(text, [r"Промежуточная страна\s+([^\n]+)"]),
        "carrier": carrier,
        "carrier_id": carrier_id,
        "driver": driver,
        "driver_id": driver_id,
        "submission_datetime": find_field(text, [r"Дата подачи\s+(\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2})"]),
        "seal_number": find_field(text, [r"Номер пломбы\s+([^\n]+)"]),
        "transport_doc_type": find_field(text, [r"Наименование документа\s+([^\n]+)"]),
        "transport_doc_number": find_field(text, [r"Номер документа\s+([^\n]+)"]),
        "transport_doc_date": find_field(text, [r"Дата выдачи\s+(\d{2}\.\d{2}\.\d{4})"]),
        "duty_payment_security": find_field(text, [r"Обеспечение исполнения обязанности по уплате\s+(.+?)(?=\nтаможенных|\nОтправитель)"]),
        "sender": sender,
        "sender_name": sender_name,
        "sender_id": sender_id,
        "receiver": receiver,
        "receiver_name": receiver_name,
        "receiver_id": receiver_id,
        "vehicles": vehicles,
        "vehicle_registration_numbers": vehicle_registration_numbers,
        "vehicle_registration_numbers_text": "\n".join(vehicle_registration_numbers),
        "vehicle_registration_numbers_compact": vehicle_registration_numbers_compact,
        "vehicle_numbers": vehicle_registration_numbers_compact,
        "truck_registration_number": split_vehicle_number(vehicle_registration_numbers[0])[0] if len(vehicle_registration_numbers) > 0 and split_vehicle_number(vehicle_registration_numbers[0]) else "",
        "trailer_registration_number": split_vehicle_number(vehicle_registration_numbers[0])[1] if len(vehicle_registration_numbers) == 1 and len(split_vehicle_number(vehicle_registration_numbers[0])) > 1 else (split_vehicle_number(vehicle_registration_numbers[1])[0] if len(vehicle_registration_numbers) > 1 and split_vehicle_number(vehicle_registration_numbers[1]) else ""),
        "goods": goods,
        "first_good_hs_code": first_good.get("hs_code", ""),
        "first_good_name": first_good.get("name", ""),
        "first_good_hs_code_and_name": " / ".join(
            part for part in [first_good.get("hs_code", ""), first_good.get("name", "")] if part
        ),
        "first_good_gross_weight_kg": first_good.get("gross_weight_kg", ""),
        "first_good_unit": first_good.get("unit", ""),
        "first_good_quantity": first_good.get("quantity", ""),
        "first_good_currency_and_value": first_good_currency_and_value,
        "first_good_country": first_good.get("country", ""),
        "first_good_shipping_document": first_good_document,
        "invoice_number": first_good.get("document_number", ""),
        "goods_count": find_field(text, [r"Общее количество наименований товаровв\s+(\d+)"]),
        "total_goods_count": find_field(text, [r"Общее количество наименований товаровв\s+(\d+)"]),
        "total_net_weight_kg": strip_trailing_zeroes(find_field(text, [r"Общая масса нетто\(кг\)\s+([\d.]+)"])),
        "total_gross_weight_kg": strip_trailing_zeroes(find_field(text, [r"Общая масса брутто\(кг\)\s+([\d.]+)"])),
        "total_cargo_places": find_field(text, [r"Общее количество грузовых мест в товарной\s+(\d+)"]),
        "total_value": strip_trailing_zeroes(find_field(text, [r"Общая стоимость товаров\s+([\d.]+)"])),
        "cargo_description": first_good.get("name", ""),
        "weight_kg": first_good.get("gross_weight_kg", ""),
        "quantity": find_field(text, [r"Общее количество грузовых мест в товарной\s+(\d+)"]),
        "route": "",
        "notes": "",
    }
    if result["origin_country"] or result["destination_country"]:
        result["route"] = f"{result['origin_country']} - {result['destination_country']}".strip(" -")
    return result


def extract_fields(pdf_path: str) -> dict[str, Any]:
    with pdfplumber.open(pdf_path) as pdf:
        full_text = "\n".join(page.extract_text(x_tolerance=1, y_tolerance=3) or "" for page in pdf.pages)
        tables = []
        for page in pdf.pages:
            tables.extend(page.extract_tables())

    preliminary = {}
    if "Предварительное информирование" in full_text:
        preliminary = parse_preliminary_information(full_text, tables)

    generic = {
        "doc_number": find_field(full_text, [
            r"(?:№|No|Number|Номер)[:\s#]+([A-Z0-9\-/]+)",
            r"(?:AWB|B/L|CMR|Invoice)[:\s#]*([A-Z0-9\-/]+)",
        ]),
        "doc_date": find_field(full_text, [
            r"(?:Date|Дата)[:\s]+(\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4})",
            r"(\d{1,2}[./\-]\d{1,2}[./\-]\d{4})",
        ]),
        "sender": find_field(full_text, [
            r"(?:Shipper|Sender|Отправитель|От кого)[:\s]+([^\n]+)",
            r"(?:From|Грузоотправитель)[:\s]+([^\n]+)",
        ]),
        "sender_address": find_field(full_text, [
            r"(?:Shipper address|Адрес отправителя)[:\s]+([^\n]+)",
        ]),
        "receiver": find_field(full_text, [
            r"(?:Consignee|Receiver|Получатель|Кому)[:\s]+([^\n]+)",
            r"(?:To|Грузополучатель)[:\s]+([^\n]+)",
        ]),
        "receiver_address": find_field(full_text, [
            r"(?:Consignee address|Адрес получателя)[:\s]+([^\n]+)",
        ]),
        "cargo_description": find_field(full_text, [
            r"(?:Description|Описание|Товар|Goods)[:\s]+([^\n]+)",
        ]),
        "weight_kg": find_field(full_text, [
            r"(?:Weight|Вес)[:\s]+([\d.,]+)\s*(?:kg|кг)",
            r"([\d.,]+)\s*(?:kg|кг)",
        ]),
        "quantity": find_field(full_text, [
            r"(?:Quantity|Количество|Pcs|Мест)[:\s]+([\d]+)",
        ]),
        "route": find_field(full_text, [
            r"(?:From|Откуда)[:\s]+([^\n]+).*?(?:To|Куда)[:\s]+([^\n]+)",
            r"(?:Route|Маршрут)[:\s]+([^\n]+)",
        ]),
        "carrier": find_field(full_text, [
            r"(?:Carrier|Перевозчик)[:\s]+([^\n]+)",
        ]),
        "notes": find_field(full_text, [
            r"(?:Remarks|Notes|Примечания|Особые отметки)[:\s]+([^\n]+)",
        ]),
        "raw_text": full_text,
    }
    generic.update({key: value for key, value in preliminary.items() if value not in ("", [], {})})
    generic["raw_text"] = full_text
    return generic
