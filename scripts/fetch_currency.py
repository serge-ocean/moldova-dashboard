#!/usr/bin/env python3
"""
Тянет официальный курс USD/EUR с НБМ (XML-фид, обновляется НБМ ежедневно)
и дописывает точку в data/currency.json.

Источник подтверждён вручную: bnm.md отдаёт XML по адресу вида
https://www.bnm.md/ro/official_exchange_rates?get_xml=1&date=DD.MM.YYYY
с элементами <Valute><CharCode>USD</CharCode><Value>19,76</Value></Valute>
"""
import json
import os
import sys
from datetime import date
from xml.etree import ElementTree as ET
import urllib.request

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "currency.json")
CURRENCIES = ["USD", "EUR"]


def fetch_today():
    today = date.today().strftime("%d.%m.%Y")
    url = f"https://www.bnm.md/ro/official_exchange_rates?get_xml=1&date={today}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        xml_data = resp.read()
    root = ET.fromstring(xml_data)
    rates = {}
    for valute in root.findall("Valute"):
        code_el = valute.find("CharCode")
        value_el = valute.find("Value")
        if code_el is None or value_el is None:
            continue
        if code_el.text in CURRENCIES:
            rates[code_el.text] = float(value_el.text.replace(",", "."))
    return rates


def load_history():
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {c: [] for c in CURRENCIES}


def save_history(history):
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def main():
    try:
        rates = fetch_today()
    except Exception as e:
        # НБМ не публикует курс в выходные/праздники — это не авария
        print(f"Не удалось получить курс: {e}")
        sys.exit(0)

    if not rates:
        print("Курс не опубликован на сегодня (возможно, выходной)")
        sys.exit(0)

    history = load_history()
    today_str = date.today().isoformat()
    for code, value in rates.items():
        history.setdefault(code, [])
        if history[code] and history[code][-1]["date"] == today_str:
            history[code][-1]["value"] = value
        else:
            history[code].append({"date": today_str, "value": value})

    save_history(history)
    print(f"OK: {rates}")


if __name__ == "__main__":
    main()
