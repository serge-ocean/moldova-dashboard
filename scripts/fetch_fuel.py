#!/usr/bin/env python3
"""
Тянет ежедневные цены-потолок на Бензин A-95 и Дизель со страницы
"Pagina consumatorului" ANRE и дописывает точку в data/fuel.json.

Источник подтверждён вручную: на https://anre.md/bpagina-consumatoruluib-3-36
есть таблица "Prețul maxim de referință" с колонками
Produse petroliere | Prețul maxim de comercializare | ...
"""
import json
import os
import re
import sys
from datetime import date
import requests
from bs4 import BeautifulSoup

URL = "https://anre.md/bpagina-consumatoruluib-3-36"
DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "fuel.json")
PRODUCTS = {"benzina95": "Benzin", "diesel": "Motorin"}  # без диакритики — надёжнее матчить


def fetch_prices():
    resp = requests.get(URL, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    prices = {}
    for tr in soup.find_all("tr"):
        text = tr.get_text(" ", strip=True)
        for key, needle in PRODUCTS.items():
            if key in prices:
                continue
            if needle.lower() in text.lower():
                m = re.search(r"\d{1,3},\d{2}", text)
                if m:
                    prices[key] = float(m.group().replace(",", "."))
    return prices


def load_history():
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {k: [] for k in PRODUCTS}


def save_history(history):
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def main():
    prices = fetch_prices()
    if not prices:
        print("Не удалось распознать цены на топливо — возможно, ANRE поменяла вёрстку страницы")
        sys.exit(1)

    history = load_history()
    today_str = date.today().isoformat()
    for key, value in prices.items():
        history.setdefault(key, [])
        if history[key] and history[key][-1]["date"] == today_str:
            history[key][-1]["value"] = value
        else:
            history[key].append({"date": today_str, "value": value})

    save_history(history)
    print(f"OK: {prices}")


if __name__ == "__main__":
    main()
