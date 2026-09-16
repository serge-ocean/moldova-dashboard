#!/usr/bin/env python3

import json
import os
import re
import unicodedata
from datetime import date

import pandas as pd
import requests
from bs4 import BeautifulSoup


DATA_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "data",
    "utilities.json",
)


SOURCES = {
    "water": {
        "url": "https://anre.md/alimentare-cu-apa-si-canalizare-3-283",
        "unit": "lei/m³",
    },
    "heating": {
        "url": "https://anre.md/energie-termica-3-247",
        "operator_match": "Termoelectrica",
        "value_col_match": "Gcal",
        "unit": "lei/Gcal",
    },
    "gas": {
        "url": "https://anre.md/gaze-naturale-3-205",
        "operator_match": "Premier Energy",
        "value_col_match": "casnici",
        "unit": "lei/m³",
    },
    "electricity": {
        "url": "https://anre.md/energie-electrica-3-290",
        "unit": "lei/kWh",
    },
}


def normalize(text):
    """
    Приводит румынский текст к простому виду:
    Chișinău -> chisinau
    joasă -> joasa
    """
    text = str(text).lower()

    text = unicodedata.normalize(
        "NFKD",
        text,
    )

    text = "".join(
        char
        for char in text
        if not unicodedata.combining(char)
    )

    return text


def number(value):
    if value is None:
        return None

    if isinstance(value, (int, float)):
        if pd.isna(value):
            return None
        return float(value)

    text = str(value).strip()

    if not text:
        return None

    text = text.replace("\xa0", " ")
    text = text.replace(",", ".")

    match = re.search(
        r"-?\d+(?:\.\d+)?",
        text,
    )

    if not match:
        return None

    try:
        return float(match.group(0))
    except ValueError:
        return None


def load_history():
    if not os.path.exists(DATA_PATH):
        return {}

    with open(
        DATA_PATH,
        "r",
        encoding="utf-8",
    ) as f:
        return json.load(f)


def save_history(history):
    os.makedirs(
        os.path.dirname(DATA_PATH),
        exist_ok=True,
    )

    with open(
        DATA_PATH,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            history,
            f,
            ensure_ascii=False,
            indent=2,
        )


def get_html(url):
    response = requests.get(
        url,
        timeout=30,
        headers={
            "User-Agent": "Mozilla/5.0"
        },
    )

    response.raise_for_status()

    return response.text


def fetch_water():
    """
    Apă-Canal Chișinău.

    Извлекает тарифы непосредственно со страницы ANRE:
    первое число после названия оператора = вода для бытовых потребителей
    третье число = канализация для бытовых потребителей

    Затем складывает их.
    """

    html = get_html(
        SOURCES["water"]["url"]
    )

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    for row in soup.find_all("tr"):

        text = row.get_text(
            " ",
            strip=True,
        )

        normalized = normalize(text)

        if "apa-canal chisinau" not in normalized:
            continue

        print(
            f"[water] найдена строка: {text}"
        )

        # Берём числа непосредственно из найденной строки.
        numbers = re.findall(
            r"\d+(?:[.,]\d+)?",
            text,
        )

        values = []

        for value in numbers:
            n = number(value)

            if n is not None:
                values.append(n)

        print(
            f"[water] извлечённые числа: {values}"
        )

        # В начале строки есть номер оператора "1".
        # Поэтому после него:
        #
        # values[1] = тариф воды для бытовых
        # values[2] = тариф воды второй категории
        # values[3] = канализация для бытовых
        #
        # Нам нужны values[1] и values[3].

        if len(values) >= 4:

            water = values[1]
            sewage = values[3]

            result = round(
                water + sewage,
                2,
            )

            print(
                f"[water] "
                f"{water} + {sewage} = "
                f"{result} lei/m³"
            )

            return result

    print(
        "[water] оператор не найден"
    )

    return None
    
def fetch_electricity():
    """
    Premier Energy.
    Универсальная услуга.
    Низкое напряжение.

    Число извлекается непосредственно
    из строки ANRE.
    """

    html = get_html(
        SOURCES["electricity"]["url"]
    )

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    rows = soup.find_all("tr")

    in_universal_section = False
    premier_found = False

    for row in rows:

        text = row.get_text(
            " ",
            strip=True,
        )

        normalized = normalize(text)

        # Начало нужной секции.
        if (
            "furnizarea energiei electrice"
            in normalized
            and "serviciului universal"
            in normalized
        ):

            in_universal_section = True
            premier_found = False

            print(
                "[electricity] "
                "найдена секция универсальной услуги"
            )

            continue

        # Следующая секция — последняя опция.
        # После неё нам искать уже не нужно.
        if (
            in_universal_section
            and "ultima optiune"
            in normalized
        ):

            print(
                "[electricity] "
                "достигнута секция последней опции"
            )

            break

        if not in_universal_section:
            continue

        # Наш оператор.
        if (
            "premier energy"
            in normalized
        ):

            premier_found = True

            print(
                "[electricity] "
                "найден Premier Energy"
            )

            # В некоторых структурах название оператора
            # может находиться в той же строке,
            # что и тариф.
            if "tensiune joasa" in normalized:

                match = re.search(
                    r"tensiune\s+joasa\s+([0-9]+(?:[.,][0-9]+)?)",
                    normalized,
                )

                if match:

                    bani = number(
                        match.group(1)
                    )

                    result = round(
                        bani / 100,
                        2,
                    )

                    print(
                        f"[electricity] "
                        f"извлечено: {bani} bani/kWh"
                    )

                    return result

            continue

        if not premier_found:
            continue

        # Ищем именно низкое напряжение
        # после Premier Energy.
        if "tensiune joasa" in normalized:

            match = re.search(
                r"tensiune\s+joasa\s+([0-9]+(?:[.,][0-9]+)?)",
                normalized,
            )

            if match:

                bani = number(
                    match.group(1)
                )

                if bani is None:
                    continue

                result = round(
                    bani / 100,
                    2,
                )

                print(
                    f"[electricity] "
                    f"извлечено: {bani} bani/kWh"
                )

                return result

    print(
        "[electricity] "
        "нужный тариф не найден"
    )

    return None


def fetch_value(key, cfg):

    if key == "water":
        return fetch_water()

    if key == "electricity":
        return fetch_electricity()

    return fetch_generic(cfg)


def main():

    history = load_history()

    today = date.today().isoformat()

    changed = False

    for key, cfg in SOURCES.items():

        print("")
        print("=" * 60)
        print(f"[{key}] начинаю поиск")
        print("=" * 60)

        try:

            value = fetch_value(
                key,
                cfg,
            )

        except Exception as error:

            print(
                f"[{key}] ОШИБКА: {error}"
            )

            continue

        if value is None:

            print(
                f"[{key}] "
                "значение не найдено"
            )

            continue

        history.setdefault(
            key,
            [],
        )

        last = (
            history[key][-1]
            if history[key]
            else None
        )

        if (
            last is None
            or last["value"] != value
        ):

            history[key].append(
                {
                    "date": today,
                    "value": value,
                    "unit": cfg["unit"],
                }
            )

            changed = True

            print(
                f"[{key}] "
                f"новое значение: "
                f"{value} {cfg['unit']}"
            )

        else:

            print(
                f"[{key}] "
                f"без изменений: "
                f"{value} {cfg['unit']}"
            )

    if changed:

        save_history(history)

        print("")
        print(
            "[OK] utilities.json обновлён"
        )

    else:

        print("")
        print(
            "[INFO] новых изменений нет"
        )


if __name__ == "__main__":
    main()
