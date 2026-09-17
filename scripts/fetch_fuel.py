#!/usr/bin/env python3
"""Fetch ANRE daily maximum reference retail prices for gasoline and diesel."""
import json
import os
import re
import sys
from datetime import date

import requests
from bs4 import BeautifulSoup

URL = "https://anre.md/bpagina-consumatoruluib-3-36"
DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "fuel.json")
PRODUCTS = {"benzina95": "benzin", "diesel": "motorin"}
HEADERS = {"User-Agent": "Mozilla/5.0"}


def normalize(text):
    return " ".join(str(text).lower().split())


def price_from_cell(text):
    match = re.search(r"\d{1,3}(?:[ .]\d{3})*,\d{2}|\d{1,3},\d{2}", text)
    if not match:
        return None
    return float(match.group(0).replace(" ", "").replace(".", "").replace(",", "."))


def find_price_column(rows):
    """Find the semantic price column even when ANRE adds title/header rows."""
    for row in rows[:8]:
        cells = row.find_all(["th", "td"])
        for index, cell in enumerate(cells):
            header = normalize(cell.get_text(" ", strip=True))
            if "pretul maxim de comercializare" in header:
                return index
    return None


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

        price_index = find_price_column(rows)

        # The current ANRE table has the product in column 1 and the
        # maximum retail price in column 2. Use this only as a structural
        # fallback when the semantic header is split across HTML rows.
        if price_index is None:
            candidate_rows = rows
        else:
            candidate_rows = rows[1:]

        for row in candidate_rows:
            cells = row.find_all(["td", "th"])
            if not cells:
                continue

            product = normalize(cells[0].get_text(" ", strip=True))
            for key, needle in PRODUCTS.items():
                if key in prices or needle not in product:
                    continue

                if price_index is not None and len(cells) > price_index:
                    value = price_from_cell(cells[price_index].get_text(" ", strip=True))
                elif len(cells) >= 2:
                    value = price_from_cell(cells[1].get_text(" ", strip=True))
                else:
                    value = None

                if value is not None:
                    prices[key] = value

    if len(prices) != len(PRODUCTS):
        missing = sorted(set(PRODUCTS) - set(prices))
        raise RuntimeError(
            "ANRE fuel table changed; could not identify maximum retail price "
            f"for: {', '.join(missing)}"
        )

    text = soup.get_text(" ", strip=True)
    date_match = re.search(
        r"(?:aplicabil pentru data de|pentru data de|pentru)\s+(\d{1,2})[./-](\d{1,2})[./-](\d{4})",
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
    entry_date = applicable_date or date.today().isoformat()

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
