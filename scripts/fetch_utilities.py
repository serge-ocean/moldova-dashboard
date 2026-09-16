#!/usr/bin/env python3

import json
import os
import re
from datetime import date

import pandas as pd


DATA_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "utilities.json"
)

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


def number(value):
    """Преобразует строку с числом ANRE в float."""
    if value is None:
        return None

    s = str(value).strip()
    s = s.replace("\xa0", " ")
    s = s.replace(",", ".")

    s = re.sub(r"[^\d.]", "", s)

    if not s:
        return None

    try:
        return float(s)
    except ValueError:
        return None


def find_row(table, text):
    """Возвращает строку таблицы, содержащую указанный текст."""
    text = text.lower()

    for idx, row in table.iterrows():
        row_text = " ".join(str(x) for x in row.tolist()).lower()

        if text in row_text:
            return row

    return None


def fetch_water():
    tables = pd.read_html(SOURCES["water"]["url"])

    for table in tables:
        row = find_row(table, "Apă-Canal Chişinău")

        if row is None:
            row = find_row(table, "Apă-Canal Chișinău")

        if row is None:
            continue

        values = []

        for value in row.tolist():
            n = number(value)
            if n is not None:
                values.append(n)

        print(f"[water] найден оператор, числа: {values}")

        # Apă-Canal Chișinău:
        # вода для бытовых потребителей = 14.03
        # канализация для бытовых потребителей = 6.63
        if len(values) >= 3:
            water = values[0]
            sewage = values[2]

            result = round(water + sewage, 2)

            print(
                f"[water] {water} + {sewage} = {result} lei/m³"
            )

            return result

    return None


def fetch_heating():
    tables = pd.read_html(SOURCES["heating"]["url"])

    for table in tables:
        row = find_row(table, "Termoelectrica")

        if row is None:
            continue

        for value in row.tolist():
            n = number(value)

            if n is not None and 1000 <= n <= 5000:
                print(f"[heating] {n} lei/Gcal")
                return n

    return None


def fetch_gas():
    tables = pd.read_html(SOURCES["gas"]["url"])

    for table in tables:
        row = find_row(table, "Energocom")

        if row is None:
            continue

        values = []

        for value in row.tolist():
            n = number(value)

            if n is not None:
                values.append(n)

        # Для низкого давления:
        # 18 798 lei / 1000 m³
        if len(values) >= 5:
            low_pressure = values[-1]
            result = round(low_pressure / 1000, 3)

            print(
                f"[gas] {low_pressure} lei/1000 m³ = "
                f"{result} lei/m³"
            )

            return result

    return None


def fetch_electricity():
    tables = pd.read_html(SOURCES["electricity"]["url"])

    for table in tables:
        premier_found = False

        for _, row in table.iterrows():
            text = " ".join(str(x) for x in row.tolist()).lower()

            if "premier energy" in text:
                premier_found = True
                print("[electricity] найден Premier Energy")
                continue

            if premier_found and "tensiune joasă" in text:
                values = []

                for value in row.tolist():
                    n = number(value)

                    if n is not None:
                        values.append(n)

                print(
                    f"[electricity] низкое напряжение: {values}"
                )

                if values:
                    # 356 bani/kWh = 3.56 lei/kWh
                    result = round(values[0] / 100, 2)

                    print(
                        f"[electricity] {values[0]} bani/kWh = "
                        f"{result} lei/kWh"
                    )

                    return result

    return None


FETCHERS = {
    "water": fetch_water,
    "heating": fetch_heating,
    "gas": fetch_gas,
    "electricity": fetch_electricity,
}


def load_history():
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    return {}


def save_history(history):
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)

    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(
            history,
            f,
            ensure_ascii=False,
            indent=2
        )


def main():
    history = load_history()
    today = date.today().isoformat()

    changed = False

    for key, fetcher in FETCHERS.items():
        try:
            value = fetcher()

        except Exception as e:
            print(f"[{key}] ошибка: {e}")
            continue

        if value is None:
            print(f"[{key}] значение не найдено")
            continue

        history.setdefault(key, [])

        last = history[key][-1] if history[key] else None

        if last is None or last["value"] != value:
            history[key].append({
                "date": today,
                "value": value,
                "unit": SOURCES[key]["unit"],
            })

            changed = True

            print(
                f"[{key}] новое значение: "
                f"{value} {SOURCES[key]['unit']}"
            )

        else:
            print(
                f"[{key}] без изменений: "
                f"{value} {SOURCES[key]['unit']}"
            )

    if changed:
        save_history(history)

        print("utilities.json обновлён")

    else:
        print("Изменений нет")


if __name__ == "__main__":
    main()
