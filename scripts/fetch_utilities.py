#!/usr/bin/env python3
"""
Тянет действующие тарифы ЖКХ, утверждённые ANRE, и дописывает точку
в data/utilities.json — но только если значение реально изменилось
(тарифы обновляются раз в несколько месяцев, а не каждый день).

ВАЖНО: таблицы ANRE для газа и электричества содержат много операторов
и категорий потребителей (напряжение, тип услуги и т.д.). Значения
operator_match / value_col_match ниже подобраны и проверены вручную
для отопления (Termoelectrica) и воды (Apă-Canal Chişinău) — сентябрь 2026.
Для газа и электричества это первое приближение — после первого прогона
сверь вывод скрипта с реальными строками таблицы на сайте ANRE и поправь
при необходимости (ссылки на страницы — в SOURCES ниже).
"""
import json
import os
from datetime import date
import pandas as pd

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "utilities.json")

SOURCES = {
    "heating": {
        "url": "https://anre.md/energie-termica-3-247",
        "operator_match": "Termoelectrica",
        "value_col_match": "Gcal",
        "unit": "lei/Gcal",
    },
    "water": {
        "url": "https://anre.md/alimentare-cu-apa-si-canalizare-3-283",
        "operator_match": "Apă-Canal Chişinău",
        "value_col_match": "casnici",  # тариф для бытовых потребителей
        "unit": "lei/m3",
    },
    "gas": {
        "url": "https://anre.md/gaze-naturale-3-205",
        "operator_match": "Premier Energy",  # ПРОВЕРИТЬ после первого запуска
        "value_col_match": "casnici",
        "unit": "lei/m3",
    },
    "electricity": {
        "url": "https://anre.md/energie-electrica-3-290",
        "operator_match": "Premier Energy",  # ПРОВЕРИТЬ: нужна строка furnizare serviciu universal / tensiune joasă
        "value_col_match": "joasă",
        "unit": "bani/kWh",
    },
}


def fetch_value(cfg):
    tables = pd.read_html(cfg["url"])
    for table in tables:
        table = table.astype(str)
        mask = table.apply(lambda col: col.str.contains(cfg["operator_match"], na=False, regex=False))
        if mask.any().any():
            row_idx = mask.any(axis=1).idxmax()
            row = table.loc[row_idx]
            for col_name, val in row.items():
                if cfg["value_col_match"].lower() in str(col_name).lower():
                    try:
                        return float(str(val).replace(",", ".").replace(" ", ""))
                    except ValueError:
                        continue
    return None


def load_history():
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_history(history):
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def main():
    history = load_history()
    today_str = date.today().isoformat()
    changed = False

    for key, cfg in SOURCES.items():
        try:
            value = fetch_value(cfg)
        except Exception as e:
            print(f"[{key}] ошибка: {e}")
            continue

        if value is None:
            print(f"[{key}] не нашёл значение — проверь operator_match/value_col_match для {cfg['url']}")
            continue

        history.setdefault(key, [])
        last = history[key][-1] if history[key] else None
        if last is None or last["value"] != value:
            history[key].append({"date": today_str, "value": value, "unit": cfg["unit"]})
            changed = True
            print(f"[{key}] новое значение: {value} {cfg['unit']}")
        else:
            print(f"[{key}] без изменений: {value} {cfg['unit']}")

    if changed:
        save_history(history)


if __name__ == "__main__":
    main()
