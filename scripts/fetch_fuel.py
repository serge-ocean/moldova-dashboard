#!/usr/bin/env python3
"""Fetch ANRE daily maximum reference retail prices for gasoline and diesel."""
import json
import os
import re
import sys

import requests
from bs4 import BeautifulSoup

URL = "https://anre.md/bpagina-consumatoruluib-3-36"
DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "fuel.json")
PRODUCTS = {"benzina95": "benzin", "diesel": "motorin"}
HEADERS = {"User-Agent": "Mozilla/5.0"}


def price_from_cell(text):
    match = re.search(r"\d{1,3}(?:[ .]\d{3})*,\d{2}|\d{1,3},\d{2}", text)
    if not match:
        return None
    return float(match.group(0).replace(" ", "").replace(".", "").replace(",", "."))


def fetch_prices():
    response = requests.get(URL, timeout=30, headers=HEADERS)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    prices = {}
    applicable_date = None

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue

        headers = [cell.get_text(" ", strip=True).lower() for cell in rows[0].find_all(["th", "td"])]
        price_index = next(
            (i for i, header in enumerate(headers)
             if "prețul maxim de comercializare" in header
             or "pretul maxim de comercializare" in header),
            None,
        )
        if price_index is None:
            continue

        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) <= price_index:
                continue
            product = cells[0].get_text(" ", strip=True).lower()
            for key, needle in PRODUCTS.items():
                if key in prices or needle not in product:
                    continue
                value = price_from_cell(cells[price_index].get_text(" ", strip=True))
                if value is not None:
                    prices[key] = value

    if len(prices) != len(PRODUCTS):
        missing = sorted(set(PRODUCTS) - set(prices))
        raise RuntimeError(
            "ANRE fuel table changed; could not identify maximum retail-price column "
            f"for: {', '.join(missing)}"
        )

    text = soup.get_text(" ", strip=True)
    date_match = re.search(
        r"(?:pentru|pentru data de)\s+(\d{1,2})[./-](\d{1,2})[./-](\d{4})",
        text,
        re.I,
    )
    if date_match:
        day, month, year = date_match.groups()
        applicable_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"

    return prices, applicable_date


def load_history():
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, "r", encoding="utf-8") as file:
            return json.load(file)
    return {key: [] for key in PRODUCTS}


def save_history(history):
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as file:
        json.dump(history, file, ensure_ascii=False, indent=2)


def main():
    prices, applicable_date = fetch_prices()
    history = load_history()
    entry_date = applicable_date or __import__("datetime").date.today().isoformat()

    for key, value in prices.items():
        history.setdefault(key, [])
        entry = {"date": entry_date, "value": value}
        if history[key] and history[key][-1]["date"] == entry_date:
            history[key][-1] = entry
        elif not history[key] or history[key][-1]["value"] != value:
            history[key].append(entry)

    save_history(history)
    print(f"OK: {prices}; applicable date: {entry_date}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"ERROR: {error}")
        sys.exit(1)
