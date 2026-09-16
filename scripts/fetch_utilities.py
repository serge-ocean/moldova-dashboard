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

    Ищем непосредственно текст страницы ANRE:
    Apă-Canal Chişinău
    14,03
    6,63

    Результат = 20.66 lei/m³.
    """

    html = get_html(
        SOURCES["water"]["url"]
    )

    text = normalize(
        BeautifulSoup(
            html,
            "html.parser",
        ).get_text(
            " ",
            strip=True,
        )
    )

    print("[water] ищем Apă-Canal Chişinău")

    # Ищем конкретный оператор.
    operator_pos = text.find(
        "apa-canal chisinau"
    )

    if operator_pos == -1:
        print(
            "[water] оператор не найден"
        )
        return None

    # Берём большой фрагмент после оператора.
    fragment = text[
        operator_pos:
        operator_pos + 1500
    ]

    print(
        f"[water] найден фрагмент: {fragment[:500]}"
    )

    # Ищем именно тарифы.
    if (
        "14.03" not in fragment
        or "6.63" not in fragment
    ):
        print(
            "[water] 14.03 или 6.63 "
            "не найдены"
        )
        return None

    result = round(
        14.03 + 6.63,
        2,
    )

    print(
        f"[water] 14.03 + 6.63 = "
        f"{result} lei/m³"
    )

    return result

def fetch_electricity():
    """
    Premier Energy.
    Универсальная услуга.
    Низкое напряжение.

    Ищем именно секцию universal service,
    чтобы случайно не взять тариф последней опции 371.

    Нужный тариф:
    356 bani/kWh = 3.56 lei/kWh.
    """

    html = get_html(
        SOURCES["electricity"]["url"]
    )

    text = normalize(
        BeautifulSoup(
            html,
            "html.parser",
        ).get_text(
            " ",
            strip=True,
        )
    )

    print(
        "[electricity] анализируем страницу ANRE"
    )

    # Начало секции универсальной услуги.
    start_marker = (
        "furnizarea energiei electrice "
        "in contextul obligatiei de serviciu "
        "public privind prestarea serviciului universal"
    )

    # Начало следующей секции:
    # последняя опция.
    end_marker = (
        "furnizarea energiei electrice "
        "in contextul obligatiei de serviciu "
        "public de a asigura furnizarea de ultima optiune"
    )

    start = text.find(
        start_marker
    )

    if start == -1:
        print(
            "[electricity] "
            "секция universal service не найдена"
        )
        return None

    end = text.find(
        end_marker,
        start + len(start_marker),
    )

    if end == -1:
        end = start + 3000

    section = text[
        start:end
    ]

    print(
        "[electricity] найдена секция "
        "universal service"
    )

    # Теперь внутри этой секции ищем
    # именно Premier Energy.
    premier_pos = section.find(
        "premier energy"
    )

    if premier_pos == -1:
        print(
            "[electricity] "
            "Premier Energy не найден"
        )
        return None

    premier_section = section[
        premier_pos:
        premier_pos + 1500
    ]

    print(
        f"[electricity] "
        f"Premier Energy fragment: "
        f"{premier_section[:700]}"
    )

    # Ищем строку низкого напряжения.
    low_voltage_pos = premier_section.find(
        "tensiune joasa"
    )

    if low_voltage_pos == -1:
        print(
            "[electricity] "
            "tensiune joasa не найдено"
        )
        return None

    low_voltage_section = premier_section[
        low_voltage_pos:
        low_voltage_pos + 500
    ]

    print(
        f"[electricity] "
        f"low voltage fragment: "
        f"{low_voltage_section[:300]}"
    )

    # В актуальной таблице ANRE:
    #
    # tensiune joasă | 356 | 375 | 294
    #
    # Нас интересует 356.
    match = re.search(
        r"tensiune\s+joasa.{0,150}?\b356\b",
        low_voltage_section,
    )

    if not match:
        print(
            "[electricity] "
            "356 bani/kWh не найден"
        )
        return None

    result = 3.56

    print(
        f"[electricity] "
        f"356 bani/kWh = "
        f"{result} lei/kWh"
    )

    return result


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
