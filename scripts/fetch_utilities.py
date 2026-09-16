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
    Ищем строку S.A. "Apă-Canal Chişinău"
    непосредственно в HTML.

    Для неё:
    14.03 = вода для бытовых потребителей
    6.63  = канализация для бытовых потребителей

    Итог: 20.66 lei/m³.
    """

    html = get_html(
        SOURCES["water"]["url"]
    )

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    target = "apa-canal chisinau"

    for row in soup.find_all("tr"):

        text = normalize(
            row.get_text(
                " ",
                strip=True,
            )
        )

        if target not in text:
            continue

        print(
            f"[water] найдена строка: {text}"
        )

        values = []

        for value in re.findall(
            r"\d+(?:[.,]\d+)?",
            text,
        ):
            n = number(value)

            if n is not None:
                values.append(n)

        print(
            f"[water] числа: {values}"
        )

        # Ожидаем:
        # 1
        # 14.03
        # 14.03
        # 6.63
        # 10.16
        # ...

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
        "[water] Apă-Canal Chişinău "
        "не найден"
    )

    return None


def fetch_electricity():
    """
    Ищем именно:

    Furnizarea energiei electrice
    ... serviciul universal

    -> Premier Energy
    -> tensiune joasă
    -> 356 bani/kWh

    Не берём тариф последней опции 371.
    """

    html = get_html(
        SOURCES["electricity"]["url"]
    )

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    universal_section = False
    premier_energy = False

    for row in soup.find_all("tr"):

        text = row.get_text(
            " ",
            strip=True,
        )

        normalized = normalize(text)

        print(
            f"[electricity] строка: {text}"
        )

        # Начало секции универсальной услуги.
        if (
            "prestarea serviciului universal"
            in normalized
        ):
            universal_section = True
            premier_energy = False

            print(
                "[electricity] "
                "найдена секция универсальной услуги"
            )

            continue

        # Начало секции последней опции.
        if "ultima optiune" in normalized:

            universal_section = False
            premier_energy = False

            print(
                "[electricity] "
                "секция последней опции пропущена"
            )

            continue

        if not universal_section:
            continue

        if (
            "premier energy"
            in normalized
        ):

            premier_energy = True

            print(
                "[electricity] "
                "найден Premier Energy"
            )

            # Иногда Premier Energy
            # и строка тарифа находятся
            # в одной HTML-строке.
            if "tensiune joasa" in normalized:

                values = [
                    number(x)
                    for x in re.findall(
                        r"\d+(?:[.,]\d+)?",
                        text,
                    )
                ]

                values = [
                    x
                    for x in values
                    if x is not None
                ]

                if values:

                    bani = values[0]

                    result = round(
                        bani / 100,
                        2,
                    )

                    print(
                        f"[electricity] "
                        f"{bani} bani/kWh = "
                        f"{result} lei/kWh"
                    )

                    return result

            continue

        if (
            premier_energy
            and "tensiune joasa"
            in normalized
        ):

            values = [
                number(x)
                for x in re.findall(
                    r"\d+(?:[.,]\d+)?",
                    text,
                )
            ]

            values = [
                x
                for x in values
                if x is not None
            ]

            print(
                f"[electricity] "
                f"низкое напряжение, "
                f"числа: {values}"
            )

            if values:

                bani = values[0]

                result = round(
                    bani / 100,
                    2,
                )

                print(
                    f"[electricity] "
                    f"{bani} bani/kWh = "
                    f"{result} lei/kWh"
                )

                return result

    print(
        "[electricity] "
        "тариф не найден"
    )

    return None


def fetch_generic(cfg):

    tables = pd.read_html(
        cfg["url"]
    )

    for table in tables:

        table_str = table.astype(str)

        mask = table_str.apply(
            lambda col: col.str.contains(
                cfg["operator_match"],
                na=False,
                regex=False,
            )
        )

        if not mask.any().any():
            continue

        row_indices = mask.any(axis=1)

        for row_idx in table.index[
            row_indices
        ]:

            row = table.loc[row_idx]

            for col_name, value in row.items():

                if (
                    cfg["value_col_match"].lower()
                    not in str(col_name).lower()
                ):
                    continue

                result = number(value)

                if result is not None:
                    return result

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
