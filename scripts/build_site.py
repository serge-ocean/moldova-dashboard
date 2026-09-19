#!/usr/bin/env python3
"""Build the static Moldova dashboard from data/*.json."""
import json
import os
from datetime import date

ROOT = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(ROOT, "data")
OUT_DIR = os.path.join(ROOT, "docs")

LABELS = {"USD":"USD","EUR":"EUR","benzina95":"Бензин A-95","diesel":"Дизель","water":"Вода","sewage":"Канализация","heating":"Отопление","gas":"Газ","electricity":"Электричество"}

def load(name):
    path = os.path.join(DATA_DIR, f"{name}.json")
    if not os.path.exists(path): return {}
    with open(path, "r", encoding="utf-8") as file: return json.load(file)

def format_value(value, key):
    if key in {"USD","EUR"}: return f"{value:.4f}".replace(".", ",")
    if key == "heating": return f"{value:.0f}"
    return f"{value:.2f}".replace(".", ",")

def trend_note(points, n=5):
    if len(points) < 2: return None
    values = [p["value"] for p in points[-n:]]
    if all(b >= a for a,b in zip(values, values[1:])) and values[-1] > values[0]: return "риск дальнейшего роста"
    if all(b <= a for a,b in zip(values, values[1:])) and values[-1] < values[0]: return "риск дальнейшего снижения"
    return None

def currency_panel_html(key, series):
    label = LABELS[key]
    if not series: return f'<section class="currency-panel"><h2>{label} (BNM)</h2><p>нет данных</p></section>'
    last, start = series[-1], series[0]
    note = trend_note(series)
    return f'''<section class="currency-panel">
      <div class="currency-head">
        <div><h2>{label} <span>(BNM)</span></h2><p>Курс на {last["date"]}</p></div>
        <div class="currency-current"><span class="diamond {key.lower()}"></span><b>{label} {format_value(last["value"], key)}</b><span class="period"><i></i>{start["date"]} – {last["date"]}</span></div>
      </div>
      <canvas id="chart-{key}"></canvas>
      {f'<p class="risk">⚠ {note}</p>' if note else ''}
    </section>'''

def daily_block_html(key, series):
    label = LABELS.get(key,key)
    if not series: return f'<div class="card"><h3>{label}</h3><p class="muted">нет данных</p></div>'
    last = series[-1]; note = trend_note(series)
    return f'''<div class="card"><h3>{label}</h3><p class="value">{format_value(last["value"],key)}</p><p class="muted">на {last["date"]}</p><canvas id="chart-{key}"></canvas>{f'<p class="risk">⚠ {note}</p>' if note else ''}</div>'''

def util_block_html(key, entries):
    label = LABELS.get(key,key)
    if not entries: return f'<div class="card"><h3>{label}</h3><p class="muted">нет данных</p></div>'
    last = entries[-1]
    return f'''<div class="card"><h3>{label}</h3><p class="value">{format_value(last["value"],key)} <span class="unit">{last.get("unit","")}</span></p><p class="muted">на {last["date"]} · НДС включён</p><canvas id="chart-{key}"></canvas></div>'''

def chart_js(key, series, currency=False):
    if not series: return ""
    labels=json.dumps([p["date"] for p in series],ensure_ascii=False); values=json.dumps([p["value"] for p in series])
    if not currency:
        return f'''new Chart(document.getElementById("chart-{key}"),{{type:"line",data:{{labels:{labels},datasets:[{{data:{values},borderColor:"#5fd97a",backgroundColor:"transparent",tension:.2,pointRadius:0}}]}},options:{{plugins:{{legend:{{display:false}}}},scales:{{x:{{display:false}},y:{{display:false}}}}}}}});'''
    border="#ef4035" if key=="USD" else "#2f80ed"
    lo=min(p["value"] for p in series); hi=max(p["value"] for p in series); spread=max(hi-lo,.05)
    return f'''new Chart(document.getElementById("chart-{key}"),{{type:"line",data:{{labels:{labels},datasets:[{{data:{values},borderColor:"{border}",backgroundColor:"transparent",borderWidth:3,tension:.15,pointRadius:5,pointHoverRadius:6,pointBackgroundColor:"{border}",pointBorderColor:"{border}"}}]}},options:{{responsive:true,maintainAspectRatio:false,layout:{{padding:{{top:30,right:28,left:6,bottom:2}}}},plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{label:ctx=>Number(ctx.raw).toFixed(4).replace('.',',')}}}}}},scales:{{x:{{grid:{{color:"rgba(255,255,255,.12)"}},ticks:{{color:"#a7adb7",maxRotation:28,minRotation:28,font:{{size:12}}}}}},y:{{min:{lo-spread*4},max:{hi+spread*4},grid:{{color:"rgba(255,255,255,.12)"}},ticks:{{color:"#a7adb7",font:{{size:12}},callback:value=>Number(value).toFixed(2).replace('.',',')}}}}}}}}}});'''

def main():
    currency,fuel,utilities=load("currency"),load("fuel"),load("utilities")
    currency_keys=[("USD",currency),("EUR",currency)]; fuel_keys=[("benzina95",fuel),("diesel",fuel)]; jkh_keys=["water","sewage","heating","gas","electricity"]
    currency_panels="".join(currency_panel_html(k,s.get(k,[])) for k,s in currency_keys)
    fuel_cards="".join(daily_block_html(k,s.get(k,[])) for k,s in fuel_keys)
    jkh_cards="".join(util_block_html(k,utilities.get(k,[])) for k in jkh_keys)
    charts="".join(chart_js(k,s.get(k,[]),True) for k,s in currency_keys)+"".join(chart_js(k,s.get(k,[])) for k,s in fuel_keys)+"".join(chart_js(k,utilities.get(k,[])) for k in jkh_keys)
    html=f'''<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>Картина дня — Кишинёв</title><meta name="viewport" content="width=device-width,initial-scale=1"><script src="https://cdn.jsdelivr.net/npm/chart.js"></script><style>
*{{box-sizing:border-box}} body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#080a0e;color:#eee;margin:0;padding:18px}} h1{{font-weight:600;font-size:21px;margin:0 0 18px}} h2{{margin:0;font-size:22px;font-weight:700;color:#f1f3f6}} .section-title{{color:#888;font-weight:500;margin:22px 0 9px;font-size:13px;text-transform:uppercase;letter-spacing:.04em}} .currency-panel{{background:#11161c;border:1px solid #252d36;border-radius:16px;padding:20px 24px 14px;margin-bottom:14px;box-shadow:0 5px 18px rgba(0,0,0,.18)}} .currency-head{{display:flex;justify-content:space-between;align-items:flex-start;gap:20px}} .currency-head h2 span{{color:#8c949f;font-weight:500}} .currency-head p{{margin:5px 0 0;color:#9ba3ad;font-size:14px}} .currency-current{{display:flex;align-items:center;gap:10px;white-space:nowrap;padding-top:3px}} .currency-current b{{font-size:24px}} .diamond{{width:13px;height:13px;transform:rotate(45deg);display:inline-block}} .diamond.usd{{background:#ef4035}} .diamond.eur{{background:#2f80ed}} .period{{color:#9ba3ad;font-size:14px;margin-left:14px;display:flex;align-items:center;gap:8px}} .period i{{width:12px;height:12px;border-radius:50%;background:#ef4035;display:inline-block}} .currency-panel canvas{{height:300px!important;width:100%!important}} .risk{{color:#ff5c5c;font-size:11px;margin:4px 0 0}} .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:9px}} .card{{background:#1b1e26;border-radius:11px;padding:11px 13px}} .card h3{{margin:0 0 3px;font-size:13px;color:#9aa;font-weight:500}} .value{{font-size:23px;font-weight:700;margin:1px 0}} .unit{{font-size:12px;color:#888;font-weight:400}} .muted{{color:#777;font-size:10.5px;margin:0;line-height:1.3}} .card canvas{{margin-top:4px;max-height:32px}} footer{{color:#555;font-size:10px;margin-top:22px}} @media(max-width:700px){{body{{padding:10px}}.currency-panel{{padding:14px 13px 10px}}.currency-head{{display:block}}.currency-current{{margin-top:12px;flex-wrap:wrap;white-space:normal}}.currency-current b{{font-size:21px}}.period{{margin-left:4px}}.currency-panel canvas{{height:250px!important}}}}
</style></head><body><h1>Картина дня — Кишинёв</h1><div class="section-title">Курс валют</div>{currency_panels}<div class="section-title">Топливо</div><div class="grid">{fuel_cards}</div><div class="section-title">ЖКХ</div><div class="grid">{jkh_cards}</div><footer>Обновлено: {date.today().isoformat()}</footer><script>{charts}</script></body></html>'''
    os.makedirs(OUT_DIR,exist_ok=True)
    with open(os.path.join(OUT_DIR,"index.html"),"w",encoding="utf-8") as file: file.write(html)
    print(f"Собрано: {os.path.join(OUT_DIR,'index.html')}")

if __name__=="__main__": main()
