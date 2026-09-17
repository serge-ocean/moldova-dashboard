#!/usr/bin/env python3
"""Fetch current regulated utility tariffs from ANRE.

All numeric values are read from the live ANRE tables. The code deliberately
contains no tariff amounts, so changes on ANRE's side are picked up
automatically.
"""
import json
import os
import re
import unicodedata

import pandas as pd
import requests


DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "utilities.json")

SOURCES = {
    "water": {
        "url": "https://anre.md/alimentare-cu-apa-si-canalizare-3-283",
        "unit": "lei/m³",
    },
    "heating": {
        "url": "https://anre.md/energie-termica-3-247",
        "unit": "lei/Gcal",
    },
    "gas": {
        "url": "https://anre.md/gaze-naturale-3-205",
        "unit": "lei/m³",
    },
    "electricity": {
        "url": "https://anre.md/energie-electrica-3-290",
        "unit": "lei/kWh",
    },
}

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140 Safari/537.36"}


def normalize(value):
    text = str(value).lower()
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def number(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).replace("\xa0", " ").strip()
    if not text:
        return None
    # ANRE uses both 18 798 and 14,03 / 20.66 styles.
    text = text.replace(" ", "")
    match = re.search(r"-?\d+(?:[.,]\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", "."))
    except ValueError:
        return None


def get_tables(url):
    response = requests.get(url, timeout=30, headers=HEADERS)
    response.raise_for_status()
    return pd.read_html(response.text)


def flatten_column(column):
    if isinstance(column, tuple):
        return " ".join(str(part) for part in column if str(part).lower() != "nan")
    return str(column)


def find_row(table, predicate):
    for index in table.index:
        row_text = " ".join(normalize(value) for value in table.loc[index].tolist())
        if predicate(row_text):
            return table.loc[index]
    return None


def value_from_column(row, column):
    return number(row[column])


def fetch_water():
    """Apă-Canal Chișinău: household drinking water + household sewerage."""
    for table in get_tables(SOURCES["water"]["url"]):
        columns = {column: normalize(flatten_column(column)) for column in table.columns}
        row = find_row(table, lambda text: "apa-canal chisinau" in text)
        if row is None:
            continue

        water_col = next(
            (col for col, name in columns.items()
             if "alimentare cu apa" in name and "consumatori casnici" in name),
            None,
        )
        sewage_col = next(
            (col for col, name in columns.items()
             if "canalizare" in name and "consumatori casnici" in name),
            None,
        )

        if water_col is None or sewage_col is None:
            continue

        water = value_from_column(row, water_col)
        sewage = value_from_column(row, sewage_col)
        if water is None or sewage is None:
            continue

        return round(water + sewage, 2)

    return None


def fetch_heating():
    """Termoelectrica tariff in lei/Gcal, without VAT."""
    for table in get_tables(SOURCES["heating"]["url"]):
        columns = {column: normalize(flatten_column(column)) for column in table.columns}
        row = find_row(table, lambda text: "termoelectrica" in text)
        if row is None:
            continue

        tariff_col = next(
            (col for col, name in columns.items() if "lei/gcal" in name),
            None,
        )
        if tariff_col is None:
            continue

        value = value_from_column(row, tariff_col)
        if value is not None:
            return value

    return None


def fetch_gas():
    """Energocom low-pressure regulated gas price, without VAT."""
    for table in get_tables(SOURCES["gas"]["url"]):
        columns = {column: normalize(flatten_column(column)) for column in table.columns}
        row = find_row(table, lambda text: "energocom" in text)
        if row is None:
            continue

        low_pressure_col = next(
            (col for col, name in columns.items() if "joasa presiune" in name),
            None,
        )
        if low_pressure_col is None:
            continue

        value_per_1000m3 = value_from_column(row, low_pressure_col)
        if value_per_1000m3 is not None:
            return round(value_per_1000m3 / 1000, 3)

    return None


def fetch_electricity():
    """Premier Energy universal-service tariff, low voltage, without VAT."""
    for table in get_tables(SOURCES["electricity"]["url"]):
        columns = {column: normalize(flatten_column(column)) for column in table.columns}

        for index in table.index:
            row = table.loc[index]
            row_text = " ".join(normalize(value) for value in row.tolist())
            if "premier energy" not in row_text or "tensiune joasa" not in row_text:
                continue

            # Prefer the explicit regulated-price column. Avoid grabbing
            # unrelated numbers such as voltage levels or decision numbers.
            tariff_col = next(
                (col for col, name in columns.items()
                 if "tarif/pret reglementat" in name and "fara tva" in name),
                None,
            )
            if tariff_col is None:
                # Some ANRE table versions put the tariff heading in a
                # MultiIndex level that flattens differently.
                tariff_col = next(
                    (col for col, name in columns.items() if "reglementat" in name and "fara tva" in name),
                    None,
                )
            if tariff_col is None:
                continue

            bani = value_from_column(row, tariff_col)
            if bani is not None:
                return round(bani / 100, 2)

    return None


def load_history():
    if not os.path.exists(DATA_PATH):
        return {}
    with open(DATA_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


def save_history(history):
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as file:
        json.dump(history, file, ensure_ascii=False, indent=2)


def main():
    fetchers = {
        "water": fetch_water,
        "heating": fetch_heating,
        "gas": fetch_gas,
        "electricity": fetch_electricity,
    }
    history = load_history()
    changed = False

    from datetime import date
    today = date.today().isoformat()

    for key, config in SOURCES.items():
        print(f"[{key}] fetching from ANRE...")
        try:
            value = fetchers[key]()
        except Exception as error:
            print(f"[{key}] ERROR: {error}")
            continue

        if value is None:
            print(f"[{key}] tariff not found; keeping previous data")
            continue

        history.setdefault(key, [])
        last = history[key][-1] if history[key] else None

        if last is None or last["value"] != value:
            history[key].append({
                "date": today,
                "value": value,
                "unit": config["unit"],
            })
            changed = True
            print(f"[{key}] new value: {value} {config['unit']}")
        else:
            print(f"[{key}] unchanged: {value} {config['unit']}")

    if changed:
        save_history(history)
        print("[OK] utilities.json updated")
    else:
        print("[INFO] no utility changes")


if __name__ == "__main__":
    main()
