#!/usr/bin/env python3

import json
import os
import re
from datetime import date

import pandas as pd


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


def number(value):
    """
    Преобразует значение таблицы в число.

    Поддерживает:
    14.03
    14,03
    "14,03 lei"
    "356 bani/kWh"
    """
    if value is None:
        return None

    if isinstance(value, (int, float)):
        if pd.isna(value):
            return None
        return float(value)

    text = str(value).strip()

    if not text or text.lower() in {"nan", "none"}:
        return None

    text = text.replace("\xa0", " ")
    text = text.replace(",", ".")

    match = re.search(r"-?\d+(?:\.\d+)?", text)

    if not match:
        return None

    try:
        return float(match.group(0))
    except ValueError:
        return None


def find_row(table, text):
    """
    Ищет строку, содержащую заданный текст.
    """
    text = text.lower()

    for _, row in table.iterrows():
        row_text = " ".join(
            str(value) for value in row.tolist()
        ).lower()

        if text in row_text:
            return row

    return None


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
            indent=2,
        )


def fetch_water():
    """
    Apă-Canal Chişinău.

    Для бытовых потребителей:
    вода = 14.03 lei/m³
    канализация = 6.63 lei/m³

    Итог:
    20.66 lei/m³
    """

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

        print(
            f"[water] найден Apă-Canal Chişinău, "
            f"числа: {values}"
        )

        # Для текущей таблицы ANRE:
        # 14.03 = вода для бытовых потребителей
        # 6.63  = канализация для бытовых потребителей
        #
        # Между ними присутствуют другие тарифные значения,
        # поэтому берём первый и третий числовые значения.

        if len(values) >= 3:

            water = values[0]
            sewage = values[2]

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

    print("[water] значение не найдено")

    return None


def fetch_electricity():
    """
    Premier Energy, универсальная услуга,
    низкое напряжение.

    ANRE:
    356 bani/kWh без НДС
    = 3.56 lei/kWh без НДС.
    """

    tables = pd.read_html(
        SOURCES["electricity"]["url"]
    )

    for table in tables:

        # Превращаем всю таблицу в последовательность строк.
        rows = []

        for _, row in table.iterrows():

            values = [
                str(value)
                for value in row.tolist()
            ]

            text = " ".join(values).strip()

            rows.append(text)

        # Ищем именно блок универсальной услуги.
        for i, text in enumerate(rows):

            text_lower = text.lower()

            if (
                "premier energy" in text_lower
                and "furnizarea" not in text_lower
            ):
                print(
                    "[electricity] найден Premier Energy"
                )

                # После строки Premier Energy идут:
                # tensiune înaltă
                # tensiune medie
                # tensiune joasă
                #
                # Нас интересует именно последняя.

                for j in range(i + 1, min(i + 10, len(rows))):

                    next_text = rows[j]
                    next_lower = next_text.lower()

                    if "tensiune joasă" not in next_lower:
                        continue

                    print(
                        "[electricity] найдена строка "
                        "tensiune joasă:"
                    )
                    print(
                        f"[electricity] {next_text}"
                    )

                    # Из строки вытаскиваем все числа.
                    values = []

                    for part in re.findall(
                        r"\d+(?:[.,]\d+)?",
                        next_text,
                    ):
                        n = number(part)

                        if n is not None:
                            values.append(n)

                    print(
                        f"[electricity] числа: {values}"
                    )

                    if values:

                        # Первый тариф — обычная цена.
                        #
                        # Например:
                        # 356 375 294
                        #
                        # 356 = обычный тариф
                        # 375 = дневной/почасовой
                        # 294 = ночной/почасовой

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
        "[electricity] значение не найдено"
    )

    return None


def fetch_generic(cfg):
    """
    Общий поиск для отопления и газа.
    """

    tables = pd.read_html(cfg["url"])

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

        for row_idx in table.index[row_indices]:

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

    today_str = date.today().isoformat()

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

        except Exception as e:

            print(
                f"[{key}] ошибка: {e}"
            )

            continue

        if value is None:

            print(
                f"[{key}] "
                f"значение не найдено"
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
                    "date": today_str,
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
