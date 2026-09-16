#!/usr/bin/env python3
"""Собирает docs/index.html из data/*.json — статичная страница-дашборд для GitHub Pages."""
import json
import os
from datetime import date

ROOT = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(ROOT, "data")
OUT_DIR = os.path.join(ROOT, "docs")

LABELS = {
    "USD": "USD / MDL",
    "EUR": "EUR / MDL",
    "benzina95": "Бензин A-95",
    "diesel": "Дизель",
    "water": "Вода / канализация",
    "heating": "Отопление (Termoelectrica)",
    "gas": "Газ",
    "electricity": "Электричество",
}


def load(name):
    path = os.path.join(DATA_DIR, f"{name}.json")
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def trend_note(points, n=5):
    """Честный тренд из данных: N точек подряд растут/падают — без каких-либо
    домыслов из новостей."""
    if len(points) < 2:
        return None
    recent = points[-n:]
    values = [p["value"] for p in recent]
    if all(b >= a for a, b in zip(values, values[1:])) and values[-1] > values[0]:
        return "риск дальнейшего роста"
    if all(b <= a for a, b in zip(values, values[1:])) and values[-1] < values[0]:
        return "риск дальнейшего снижения"
    return None


def daily_block_html(key, series):
    label = LABELS.get(key, key)
    if not series:
        return f'<div class="card"><h3>{label}</h3><p class="muted">нет данных</p></div>'
    last = series[-1]
    note = trend_note(series)
    note_html = f'<p class="risk">⚠ {note}</p>' if note else ""
    return f'''
    <div class="card">
      <h3>{label}</h3>
      <p class="value">{last["value"]}</p>
      <p class="muted">на {last["date"]}</p>
      <canvas id="chart-{key}"></canvas>
      {note_html}
    </div>'''


def util_block_html(key, entries):
    label = LABELS.get(key, key)
    if not entries:
        return f'<div class="card"><h3>{label}</h3><p class="muted">нет данных</p></div>'
    last = entries[-1]
    return f'''
    <div class="card">
      <h3>{label}</h3>
      <p class="value">{last["value"]} <span class="unit">{last.get("unit", "")}</span></p>
      <p class="muted">тариф действует с {last["date"]}</p>
      <canvas id="chart-{key}"></canvas>
    </div>'''


def chart_js(key, series):
    if not series:
        return ""
    labels = json.dumps([p["date"] for p in series])
    values = json.dumps([p["value"] for p in series])
    return f'''
    new Chart(document.getElementById("chart-{key}"), {{
      type: "line",
      data: {{ labels: {labels}, datasets: [{{ data: {values}, borderColor: "#5fd97a", backgroundColor: "transparent", tension: 0.2, pointRadius: 0 }}] }},
      options: {{ plugins: {{ legend: {{ display: false }} }}, scales: {{ x: {{ display: false }}, y: {{ display: false }} }} }}
    }});'''


def main():
    currency = load("currency")
    fuel = load("fuel")
    utilities = load("utilities")

    economy_keys_daily = [("USD", currency), ("EUR", currency), ("benzina95", fuel), ("diesel", fuel)]
    jkh_keys = ["water", "heating", "gas", "electricity"]

    economy_cards = "".join(daily_block_html(k, src.get(k, [])) for k, src in economy_keys_daily)
    jkh_cards = "".join(util_block_html(k, utilities.get(k, [])) for k in jkh_keys)

    charts_js = "".join(chart_js(k, src.get(k, [])) for k, src in economy_keys_daily)
    charts_js += "".join(chart_js(k, utilities.get(k, [])) for k in jkh_keys)

    html = f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Картина дня — Кишинёв</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background:#111318; color:#eee; margin:0; padding:24px; }}
  h1 {{ font-weight:600; font-size:22px; }}
  h2 {{ color:#888; font-weight:500; margin-top:32px; font-size:15px; text-transform:uppercase; letter-spacing:0.04em; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:14px; }}
  .card {{ background:#1b1e26; border-radius:14px; padding:16px 18px; }}
  .card h3 {{ margin:0 0 6px; font-size:14px; color:#9aa; font-weight:500; }}
  .value {{ font-size:26px; font-weight:700; margin:2px 0; }}
  .unit {{ font-size:14px; color:#888; font-weight:400; }}
  .muted {{ color:#777; font-size:12px; margin:0; }}
  .risk {{ color:#ff5c5c; font-size:12.5px; margin-top:8px; margin-bottom:0; }}
  canvas {{ margin-top:8px; max-height:50px; }}
  footer {{ color:#555; font-size:12px; margin-top:40px; }}
</style>
</head>
<body>
  <h1>Картина дня — Кишинёв</h1>
  <h2>Экономика</h2>
  <div class="grid">{economy_cards}</div>
  <h2>ЖКХ</h2>
  <div class="grid">{jkh_cards}</div>
  <footer>Обновлено: {date.today().isoformat()}</footer>
  <script>{charts_js}</script>
</body>
</html>"""

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Собрано: {os.path.join(OUT_DIR, 'index.html')}")


if __name__ == "__main__":
    main()
