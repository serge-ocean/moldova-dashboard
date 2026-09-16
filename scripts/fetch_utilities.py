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
    Убирает регистр и диакритику:
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
    """
    Преобразует строку/ячейку в число.
    """

    if value is None:
        return None

    if isinstance(value, (int, float)):

        if pd.isna(value):
            return None

        return float(value)

    text = str(value).strip()

    if not text:
        return None

    text = text.replace(
        "\xa0",
        " ",
    )

    text = text.replace(
        ",",
        ".",
    )

    match = re.search(
        r"-?\d+(?:\.\d+)?",
        text,
    )

    if not match:
        return None

    try:
        return float(
            match.group(0)
        )
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
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "Chrome/140 Safari/537.36"
            )
        },
    )

    response.raise_for_status()

    return response.text


def fetch_water():
    """
    Извлекает тарифы Apă-Canal Chișinău
    непосредственно из таблицы ANRE.

    В строке оператора находятся тарифы:

    - вода для бытовых потребителей;
    - вода для других категорий;
    - канализация для бытовых потребителей;
    - канализация для небытовых потребителей;
    - другие тарифы.

    Берём первый и третий тарифных показателя.
    Никаких конкретных значений в коде нет.
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

        if (
            "apa-canal chisinau"
            not in normalized
        ):
            continue

        print(
            "[water] найден оператор:"
        )

        print(text)

        # Сначала получаем содержимое
        # отдельных ячеек.
        cells = row.find_all(
            ["td", "th"]
        )

        numeric_values = []

        for cell in cells:

            cell_text = cell.get_text(
                " ",
                strip=True,
            )

            value = number(
                cell_text
            )

            if value is not None:
                numeric_values.append(
                    value
                )

        print(
            f"[water] числа из ячеек: "
            f"{numeric_values}"
        )

        # Первая цифра обычно является
        # номером строки (1).
        #
        # После неё идут тарифы.
        #
        # Поэтому отбрасываем целочисленный
        # номер строки, если он присутствует.

        tariff_values = [
            value
            for value in numeric_values
            if value != int(value)
        ]

        print(
            f"[water] тарифные значения: "
            f"{tariff_values}"
        )

        if len(tariff_values) >= 3:

            water = tariff_values[0]
            sewage = tariff_values[2]

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
            "[water] недостаточно "
            "тарифных значений"
        )

    print(
        "[water] оператор не найден"
    )

    return None


def fetch_electricity():
    """
    Premier Energy.

    Ищем именно секцию:

    Furnizarea energiei electrice...
    privind prestarea serviciului universal

    Затем:
    Premier Energy
    -> tensiune joasă

    Из строки tensiune joasă
    извлекаем первый тариф.

    Никакого 356 в коде нет.
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

        normalized = normalize(
            text
        )

        # Находим начало секции
        # универсальной услуги.
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
                "найдена секция "
                "универсальной услуги"
            )

            continue

        # Дошли до секции
        # последней опции.
        if (
            in_universal_section
            and "ultima optiune"
            in normalized
        ):

            print(
                "[electricity] "
                "достигнут конец "
                "нужной секции"
            )

            break

        if not in_universal_section:
            continue

        # Нашли Premier Energy.
        if (
            "premier energy"
            in normalized
        ):

            premier_found = True

            print(
                "[electricity] "
                "найден Premier Energy"
            )

            # Иногда название оператора
            # и тарифная строка находятся
            # в одной строке.
            if (
                "tensiune joasa"
                in normalized
            ):

                values = []

                for cell in row.find_all(
                    ["td", "th"]
                ):

                    value = number(
                        cell.get_text(
                            " ",
                            strip=True,
                        )
                    )

                    if value is not None:
                        values.append(value)

                if values:

                    bani = values[0]

                    result = round(
                        bani / 100,
                        2,
                    )

                    print(
                        f"[electricity] "
                        f"извлечено: "
                        f"{bani} bani/kWh"
                    )

                    return result

            continue

        if not premier_found:
            continue

        # Ищем строку:
        # tensiune joasă
        if (
            "tensiune joasa"
            not in normalized
        ):
            continue

        print(
            "[electricity] "
            f"найдена строка: {text}"
        )

        values = []

        # Берём числа из отдельных
        # ячеек таблицы.
        for cell in row.find_all(
            ["td", "th"]
        ):

            value = number(
                cell.get_text(
                    " ",
                    strip=True,
                )
            )

            if value is not None:
                values.append(value)

        print(
            f"[electricity] "
            f"числа строки: {values}"
        )

        if not values:
            continue

        # Первый тариф — основной
        # регулируемый тариф.
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
        "нужный тариф не найден"
    )

    return None


def fetch_generic(cfg):
    """
    Общий парсер для отопления и газа.
    """

    tables = pd.read_html(
        cfg["url"]
    )

    for table in tables:

        table_str = table.astype(
            str
        )

        mask = table_str.apply(
            lambda column: column.str.contains(
                cfg["operator_match"],
                na=False,
                regex=False,
            )
        )

        if not mask.any().any():
            continue

        row_indices = mask.any(
            axis=1
        )

        for row_idx in table.index[
            row_indices
        ]:

            row = table.loc[row_idx]

            for col_name, value in row.items():

                if (
                    cfg["value_col_match"].lower()
                    not in str(
                        col_name
                    ).lower()
                ):
                    continue

                result = number(
                    value
                )

                if result is not None:

                    print(
                        f"[generic] "
                        f"{result} "
                        f"{cfg['unit']}"
                    )

                    return result

    return None


def fetch_value(
    key,
    cfg,
):

    if key == "water":
        return fetch_water()

    if key == "electricity":
        return fetch_electricity()

    return fetch_generic(
        cfg
    )


def main():

    history = load_history()

    today = date.today().isoformat()

    changed = False

    for key, cfg in SOURCES.items():

        print("")
        print(
            "=" * 60
        )
        print(
            f"[{key}] начинаю поиск"
        )
        print(
            "=" * 60
        )

        try:

            value = fetch_value(
                key,
                cfg,
            )

        except Exception as error:

            print(
                f"[{key}] ОШИБКА: "
                f"{error}"
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
                f"{value} "
                f"{cfg['unit']}"
            )

        else:

            print(
                f"[{key}] "
                f"без изменений: "
                f"{value} "
                f"{cfg['unit']}"
            )

    if changed:

        save_history(
            history
        )

        print("")
        print(
            "[OK] utilities.json "
            "обновлён"
        )

    else:

        print("")
        print(
            "[INFO] новых изменений "
            "нет"
        )


if __name__ == "__main__":
    main()
