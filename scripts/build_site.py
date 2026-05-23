"""
Genera il sito statico in docs/index.html a partire dai dati in data/*.json.

Pattern:
  - Legge i JSON delle serie storiche
  - Genera i grafici con Plotly (HTML standalone, plotly.js da CDN)
  - Inserisce i grafici nel template HTML mantenendo stile/struttura
  - Scrive il risultato in docs/index.html

Il template HTML è inline qui sotto per semplicità. Se vuoi separarlo,
sposta TEMPLATE in docs/template.html e leggilo da file.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import plotly.graph_objects as go
import plotly.io as pio

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUTPUT_HTML = ROOT / "docs" / "index.html"

# Palette coerente con il template HTML sotto
COLOR_BG = "#faf8f3"
COLOR_FG = "#1a1a1a"
COLOR_GRID = "#e8e2d2"
COLOR_BEV = "#1d6f42"        # verde scuro per BEV
COLOR_BEV_LINE = "#c9542e"   # accento ruggine per share
COLOR_PAY = "#2c4a7a"        # blu scuro per operazioni
COLOR_PAY_LINE = "#b8893a"   # accento oro per valore

# Palette operatori telefonici (coerenti coi brand ma armoniche col resto del sito)
COLOR_OPERATORS = {
    "TIM": "#c0392b",              # rosso TIM
    "Vodafone+Fastweb": "#3d5a80", # blu navy
    "WindTre": "#d68438",          # arancio bruciato
    "Iliad": "#1a1a1a",            # nero
}

# Font Plotly — il sito carica Fraunces e Geist via Google Fonts
FONT_FAMILY = "Geist, system-ui, sans-serif"


def common_layout() -> dict:
    """Layout Plotly base condiviso da tutti i grafici.

    Il titolo del grafico NON è impostato qui: usiamo l'h2 della sezione HTML
    come titolo (più leggibile, e su mobile non occupa spazio prezioso sopra
    al chart). La legenda è sotto al grafico per lo stesso motivo.
    """
    return dict(
        paper_bgcolor=COLOR_BG,
        plot_bgcolor=COLOR_BG,
        font=dict(family=FONT_FAMILY, color=COLOR_FG, size=12),
        margin=dict(l=48, r=48, t=60, b=72),  # top maggiore per range buttons
        hovermode="x unified",
        xaxis=dict(showgrid=False, linecolor=COLOR_GRID, automargin=True),
        yaxis=dict(gridcolor=COLOR_GRID, zerolinecolor=COLOR_GRID, automargin=True),
        legend=dict(
            orientation="h",
            yanchor="top", y=-0.18,
            xanchor="center", x=0.5,
            font=dict(size=12),
        ),
    )


def chart_config(static: bool = False) -> dict:
    """Config Plotly comune. static=True disabilita ogni interazione (per chart snapshot)."""
    return {
        "displayModeBar": False,
        "responsive": True,
        "scrollZoom": False,
        "doubleClick": False,
        "staticPlot": static,
    }


def rangeselector(buttons: list) -> dict:
    """Range selector buttons sopra al grafico, stile coerente col resto del sito.

    Uso un grigio chiaro neutro per il bottone attivo (invece di un colore brand)
    così il testo scuro resta sempre leggibile.
    """
    return dict(
        buttons=buttons,
        x=0, y=1.18,
        xanchor="left", yanchor="top",
        bgcolor=COLOR_BG,
        bordercolor=COLOR_GRID,
        borderwidth=1,
        font=dict(family=FONT_FAMILY, color=COLOR_FG, size=11),
        activecolor=COLOR_GRID,  # grigio chiaro: testo scuro sempre leggibile sopra
    )


def chart_bev(data: dict) -> str:
    from datetime import timedelta
    # Mostra SEMPRE solo gli ultimi 24 mesi
    obs = data["observations"][-24:]
    periods = [datetime.strptime(o["period"], "%Y-%m").replace(day=15) for o in obs]
    regs = [o["registrations"] for o in obs]
    shares = [o.get("market_share_pct") for o in obs]

    BAR_WIDTH_MS = 2.0e9  # ~23 giorni

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=periods, y=regs, name="Immatricolazioni",
        marker_color=COLOR_BEV,
        width=BAR_WIDTH_MS,
        cliponaxis=False,
        hovertemplate="<b>%{x|%b %Y}</b><br>%{y:,} immatricolazioni<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=periods, y=shares, name="Market share %",
        mode="lines+markers", yaxis="y2",
        line=dict(color=COLOR_BEV_LINE, width=2.5),
        marker=dict(size=7),
        cliponaxis=False,
        hovertemplate="<b>%{x|%b %Y}</b><br>%{y}%% market share<extra></extra>",
    ))
    layout = common_layout()
    layout["margin"] = dict(l=60, r=60, t=30, b=50)
    # Range esplicito = primo e ultimo dato visualizzato, con padding mezza-barra
    layout["xaxis"] = dict(
        type="date", showgrid=False, linecolor=COLOR_GRID,
        range=[periods[0] - timedelta(days=25), periods[-1] + timedelta(days=25)],
    )
    layout["yaxis"] = dict(title="", gridcolor=COLOR_GRID, zerolinecolor=COLOR_GRID, automargin=True)
    layout["yaxis2"] = dict(title="", overlaying="y", side="right", showgrid=False,
                           ticksuffix="%", automargin=True)
    fig.update_layout(**layout)

    return pio.to_html(fig, include_plotlyjs="cdn", full_html=False, div_id="chart-bev",
                       config=chart_config(static=False))


def chart_payments(data: dict) -> str:
    # Mostra SEMPRE solo gli ultimi 10 anni
    obs = data["observations"][-10:]
    years_dt = [datetime(o["year"], 1, 1) for o in obs]
    cashless = [o["cashless_pct"] for o in obs]
    cash = [o["cash_pct"] for o in obs]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=years_dt, y=cashless, name="Pagamenti elettronici",
        mode="lines+markers",
        line=dict(color=COLOR_PAY, width=3),
        marker=dict(size=9),
        cliponaxis=False,
        hovertemplate="<b>%{x|%Y}</b><br>Cashless: %{y}%% dei consumi<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=years_dt, y=cash, name="Contanti",
        mode="lines+markers",
        line=dict(color=COLOR_PAY_LINE, width=3, dash="dot"),
        marker=dict(size=9),
        cliponaxis=False,
        hovertemplate="<b>%{x|%Y}</b><br>Contante: %{y}%% dei consumi<extra></extra>",
    ))
    layout = common_layout()
    layout["margin"] = dict(l=60, r=60, t=30, b=50)
    # Range esplicito = dal 6 mesi prima del primo punto al 31 dicembre dell'ultimo anno
    first_year = years_dt[0].year
    last_year = years_dt[-1].year
    layout["xaxis"] = dict(
        type="date", showgrid=False, linecolor=COLOR_GRID,
        tickformat="%Y",
        range=[
            datetime(first_year - 1, 1, 1),     # 1 anno intero di padding a sx
            datetime(last_year, 12, 31),         # fino al 31 dic ultimo anno (no 2026)
        ],
    )
    layout["yaxis"] = dict(title="", gridcolor=COLOR_GRID, zerolinecolor=COLOR_GRID,
                          automargin=True, ticksuffix="%", range=[0, 70])
    fig.update_layout(**layout)

    return pio.to_html(fig, include_plotlyjs=False, full_html=False, div_id="chart-payments",
                       config=chart_config(static=False))


def chart_mobile(data: dict) -> str:
    """
    Bar chart verticale dell'ultimo trimestre, ordinato per quota decrescente.
    Sopra ogni barra: quota % + variazione vs lo stesso trimestre di un anno fa.
    """
    obs = data["observations"]
    operators = data["operators"]
    if not obs:
        return ""

    latest = obs[-1]
    latest_period = latest["period"]  # es. "2025-Q4"
    year, q = latest_period.split("-")
    yoy_period = f"{int(year) - 1}-{q}"
    yoy = next((o for o in obs if o["period"] == yoy_period), None)

    sorted_ops = sorted(operators, key=lambda op: latest.get(op, 0), reverse=True)
    values = [latest.get(op, 0) for op in sorted_ops]

    deltas = []
    for op in sorted_ops:
        if yoy and yoy.get(op) is not None:
            deltas.append(latest.get(op, 0) - yoy.get(op, 0))
        else:
            deltas.append(None)

    # Etichette su due righe: prima la quota, poi la delta (più leggibile su mobile)
    text_labels = []
    for v, d in zip(values, deltas):
        if d is None:
            text_labels.append(f"<b>{v:.1f}%</b>")
        elif d > 0.05:
            text_labels.append(f"<b>{v:.1f}%</b><br>▲ +{d:.1f} pp")
        elif d < -0.05:
            text_labels.append(f"<b>{v:.1f}%</b><br>▼ {d:.1f} pp")
        else:
            text_labels.append(f"<b>{v:.1f}%</b><br>≈ 0")

    colors = [COLOR_OPERATORS.get(op, "#666") for op in sorted_ops]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=sorted_ops,
        y=values,
        marker_color=colors,
        text=text_labels,
        textposition="outside",
        textfont=dict(family=FONT_FAMILY, size=12, color=COLOR_FG),
        cliponaxis=False,
    ))

    layout = common_layout()
    layout["xaxis"] = dict(
        showgrid=False, automargin=True,
        tickfont=dict(size=12),
    )
    layout["yaxis"] = dict(
        showgrid=True, gridcolor=COLOR_GRID,
        ticksuffix="%", range=[0, max(values) * 1.30],  # spazio per label sopra
        automargin=True,
    )
    layout["showlegend"] = False
    layout["margin"] = dict(l=40, r=20, t=40, b=40)
    fig.update_layout(**layout)

    return pio.to_html(fig, include_plotlyjs=False, full_html=False, div_id="chart-mobile",
                       config=chart_config(static=True))


def chart_banks(data: dict) -> str:
    """Bar chart orizzontale: snapshot ultimo anno disponibile + delta % vs primo anno.

    Pattern stilistico simile a chart_mobile (operatori), ma orizzontale perché
    i nomi delle banche sono lunghi e meritano spazio a sinistra.
    """
    # Mostra SEMPRE solo gli ultimi 10 anni di dati nel JSON, ma il delta
    # si calcola SOLO rispetto all'anno precedente (snapshot anno su anno).
    obs = data["observations"][-10:]
    banks = data["banks"]
    prev_obs = obs[-2]    # anno precedente per calcolo delta
    last_obs = obs[-1]
    prev_year = prev_obs["year"]
    last_year = last_obs["year"]

    rows = []
    for bank in banks:
        name = bank["name"]
        v_now = last_obs.get(name)
        v_prev = prev_obs.get(name)
        if v_now is None or v_prev is None or v_prev == 0:
            continue
        delta_pct = (v_now - v_prev) / v_prev * 100
        rows.append({
            "name": name, "color": bank["color"],
            "value": v_now, "delta_pct": delta_pct,
        })
    # Ordina per dimensione decrescente. Plotly bar orizzontale disegna
    # dal basso verso l'alto, quindi inverto per avere il più grande in cima
    rows.sort(key=lambda r: r["value"], reverse=True)
    rows = rows[::-1]

    names = [r["name"] for r in rows]
    values = [r["value"] for r in rows]
    colors = [r["color"] for r in rows]

    # Label fuori barra: "13.6M  ▲ +23%"  /  "0.05M → 4.0M  ▲ +7.9k%"
    def fmt_delta(d: float) -> str:
        if abs(d) >= 1000:
            return f"+{d/1000:.1f}k%" if d > 0 else f"-{abs(d)/1000:.1f}k%"
        return f"{d:+.0f}%"

    labels = []
    for r in rows:
        arrow = "▲" if r["delta_pct"] >= 0 else "▼"
        labels.append(f"<b>{r['value']:.1f}M</b>   {arrow} {fmt_delta(r['delta_pct'])}")

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=values, y=names,
        orientation="h",
        marker_color=colors,
        text=labels,
        textposition="outside",
        textfont=dict(size=12),
        cliponaxis=False,
        hovertemplate=(
            "<b>%{y}</b><br>"
            f"Clienti {last_year}: %{{x}}M<br>"
            f"Variazione vs {prev_year}: %{{customdata}}<extra></extra>"
        ),
        customdata=[fmt_delta(r["delta_pct"]) for r in rows],
    ))

    layout = common_layout()
    layout["margin"] = dict(l=130, r=140, t=20, b=30)  # spazio nomi sx + label dx
    layout["xaxis"] = dict(
        showgrid=False, showticklabels=False, zeroline=False,
        range=[0, max(values) * 1.45],  # spazio extra per le label "outside"
    )
    layout["yaxis"] = dict(
        showgrid=False, automargin=True,
        tickfont=dict(size=13),
    )
    layout["showlegend"] = False
    fig.update_layout(**layout)
    return pio.to_html(fig, include_plotlyjs=False, full_html=False, div_id="chart-banks",
                       config=chart_config(static=True))


def chart_desertification(data: dict) -> str:
    """Bar chart annuale del numero di sportelli bancari in Italia.

    Storia: la rete bancaria fisica si è quasi dimezzata in 15 anni.
    """
    obs = data["observations"][-10:]
    years_dt = [datetime(o["year"], 1, 1) for o in obs]
    sportelli = [o["sportelli"] for o in obs]

    # Bar chart con barre marrone-bruno (evoca "ritirata" / colore terra)
    COLOR_DESERT = "#8a5a3f"

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=years_dt, y=sportelli, name="Sportelli",
        marker_color=COLOR_DESERT,
        width=2.0e10,  # barre larghe (anni interi, non mesi → width molto maggiore)
        cliponaxis=False,
        hovertemplate="<b>%{x|%Y}</b><br>%{y:,} sportelli<extra></extra>",
    ))
    layout = common_layout()
    layout["margin"] = dict(l=60, r=60, t=30, b=50)
    layout["showlegend"] = False
    first_year = years_dt[0].year
    last_year = years_dt[-1].year
    layout["xaxis"] = dict(
        type="date", showgrid=False, linecolor=COLOR_GRID,
        tickformat="%Y",
        range=[datetime(first_year - 1, 1, 1), datetime(last_year, 12, 31)],
    )
    layout["yaxis"] = dict(
        gridcolor=COLOR_GRID, zerolinecolor=COLOR_GRID, automargin=True,
        rangemode="tozero",
    )
    fig.update_layout(**layout)
    return pio.to_html(fig, include_plotlyjs=False, full_html=False, div_id="chart-desertification",
                       config=chart_config(static=True))


def chart_energy_mix(data: dict) -> str:
    """Stacked area chart del mix di generazione elettrica italiana, ultimi 24 mesi.

    6 fonti aggregate per leggibilità: gas, solare, idro, eolico, altre rinnovabili, altre fossili.
    """
    from datetime import timedelta
    obs = data.get("observations", [])
    if not obs:
        # Placeholder finché l'API non è attiva
        return ('<div style="padding:60px 20px;text-align:center;color:#8a7a55;'
                'font-style:italic;">Dati in attesa di prima chiamata API ENTSO-E. '
                'Il grafico apparirà al primo aggiornamento utile.</div>')

    obs = obs[-24:]
    periods = [datetime.strptime(o["period"], "%Y-%m").replace(day=15) for o in obs]

    # Palette: ordine narrativo (fossili in fondo grigio, rinnovabili sopra a colori)
    # In stacked area, l'ORDINE conta: il primo trace sta sotto.
    layers = [
        ("altre_fossili",     "Altre fossili",       "#2f2f2f"),
        ("gas",                "Gas naturale",        "#6f6f6f"),
        ("idro",               "Idroelettrico",       "#4a6f9a"),
        ("eolico",             "Eolico",              "#5d9b8c"),
        ("solare",             "Solare",              "#d6ad3e"),
        ("altre_rinnovabili",  "Altre rinnovabili",   "#7d9b5a"),
    ]

    fig = go.Figure()
    for key, label, color in layers:
        values = [o.get(key, 0) for o in obs]
        fig.add_trace(go.Scatter(
            x=periods, y=values, name=label,
            stackgroup="one",
            mode="none",  # solo riempimento, niente linea
            fillcolor=color,
            cliponaxis=False,
            hovertemplate=f"<b>{label}</b><br>%{{x|%b %Y}}: %{{y:.1f}} TWh<extra></extra>",
        ))
    layout = common_layout()
    layout["margin"] = dict(l=60, r=60, t=30, b=50)
    layout["xaxis"] = dict(
        type="date", showgrid=False, linecolor=COLOR_GRID,
        range=[periods[0] - timedelta(days=20), periods[-1] + timedelta(days=20)],
    )
    layout["yaxis"] = dict(
        gridcolor=COLOR_GRID, zerolinecolor=COLOR_GRID, automargin=True,
        ticksuffix=" TWh", rangemode="tozero",
    )
    layout["hovermode"] = "x unified"
    fig.update_layout(**layout)
    return pio.to_html(fig, include_plotlyjs=False, full_html=False, div_id="chart-energy-mix",
                       config=chart_config(static=True))


TEMPLATE = """<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Osservatorio Italia — Dati mensili</title>
  <meta name="description" content="Monitoraggio mensile di indicatori italiani: auto elettriche e pagamenti elettronici.">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,700&family=Geist:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #faf8f3;
      --fg: #1a1a1a;
      --fg-soft: #5a5651;
      --rule: #d4cfc1;
      --accent-bev: #1d6f42;
      --accent-pay: #2c4a7a;
    }
    * { box-sizing: border-box; }
    html, body { margin: 0; padding: 0; background: var(--bg); color: var(--fg); }
    body { font-family: "Geist", system-ui, sans-serif; line-height: 1.5; -webkit-font-smoothing: antialiased; }

    .wrap { max-width: 1080px; margin: 0 auto; padding: 64px 32px 96px; }

    header { border-bottom: 1px solid var(--rule); padding-bottom: 28px; margin-bottom: 56px; }
    .eyebrow { font-family: "Geist", sans-serif; text-transform: uppercase; letter-spacing: 0.18em; font-size: 11px; color: var(--fg-soft); margin: 0 0 12px; }
    h1 { font-family: "Fraunces", serif; font-weight: 500; font-size: clamp(38px, 5vw, 60px); line-height: 1.05; margin: 0 0 16px; letter-spacing: -0.01em; font-variation-settings: "opsz" 144; }
    h1 em { font-style: italic; font-weight: 400; color: var(--fg-soft); }
    .lede { font-family: "Fraunces", serif; font-size: 18px; line-height: 1.55; max-width: 62ch; color: var(--fg-soft); margin: 0; }

    .meta { display: flex; gap: 24px; flex-wrap: wrap; margin-top: 24px; font-size: 13px; color: var(--fg-soft); }
    .meta span strong { color: var(--fg); font-weight: 500; }

    section.card { margin-bottom: 80px; }
    section.card h2 { font-family: "Fraunces", serif; font-weight: 500; font-size: 28px; margin: 0 0 6px; letter-spacing: -0.005em; }
    section.card .sub { color: var(--fg-soft); font-size: 14px; margin: 0 0 28px; }
    section.card .source { font-size: 12px; color: var(--fg-soft); margin-top: 8px; text-align: right; }
    section.card .source a { color: inherit; text-underline-offset: 2px; }

    .chart-wrap { background: var(--bg); padding: 0; border-top: 1px solid var(--rule); border-bottom: 1px solid var(--rule); touch-action: pan-y; }

    /* Su dispositivi touch (mobile, tablet) i grafici Plotly diventano
       totalmente statici: niente hover, niente drag, niente pinch.
       Lo scroll della pagina passa attraverso il grafico senza che
       venga interpretato come pan/zoom interno. */
    @media (pointer: coarse) {
      .chart-wrap .js-plotly-plot,
      .chart-wrap .js-plotly-plot * { pointer-events: none !important; }
    }

    footer { margin-top: 96px; padding-top: 28px; border-top: 1px solid var(--rule); font-size: 12px; color: var(--fg-soft); display: flex; justify-content: space-between; flex-wrap: wrap; gap: 16px; }

    @media (max-width: 640px) {
      .wrap { padding: 32px 16px 56px; }
      header { margin-bottom: 40px; }
      h1 { font-size: 36px; }
      .lede { font-size: 16px; }
      section.card { margin-bottom: 56px; }
      section.card h2 { font-size: 22px; }
      section.card .sub { font-size: 13px; }
      .chart-wrap { margin: 0 -16px; padding: 0; } /* il grafico va edge-to-edge su mobile */
    }
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <p class="eyebrow">Osservatorio Italia</p>
      <h1>Dati mensili <em>dall'Italia che cambia</em></h1>
      <p class="lede">Un monitoraggio essenziale di due indicatori che raccontano la transizione in corso: la diffusione dell'auto elettrica e l'uso dei pagamenti digitali.</p>
      <div class="meta">
        <span>Ultimo aggiornamento: <strong>__UPDATED_AT__</strong></span>
        <span>Cadenza: <strong>mensile</strong></span>
      </div>
    </header>

    __TOPICS__

    <footer>
      <span>Generato automaticamente · build __BUILD_DATE__</span>
      <span>Codice e dati: <a href="#" style="color:inherit">repo GitHub</a></span>
    </footer>
  </div>
</body>
</html>
"""


def render_topic(t: dict) -> str:
    """Renderizza una singola sezione topic.

    `t` è un dict con: title, subtitle, chart_html, source_html, updated_at.
    Mostra anche la data dell'ultimo aggiornamento sotto al titolo,
    per dare contesto su 'perché è in questa posizione'.
    """
    return f"""    <section class="card">
      <h2>{t['title']}</h2>
      <p class="sub">{t['subtitle']}</p>
      <div class="chart-wrap">
        {t['chart_html']}
      </div>
      <p class="source">{t['source_html']}</p>
    </section>"""


def main() -> int:
    with open(DATA_DIR / "bev_italia.json", "r", encoding="utf-8") as f:
        bev_data = json.load(f)
    with open(DATA_DIR / "pagamenti_italia.json", "r", encoding="utf-8") as f:
        pay_data = json.load(f)
    with open(DATA_DIR / "operatori_mobile.json", "r", encoding="utf-8") as f:
        mob_data = json.load(f)
    with open(DATA_DIR / "banche_italia.json", "r", encoding="utf-8") as f:
        banks_data = json.load(f)
    with open(DATA_DIR / "desertificazione_bancaria.json", "r", encoding="utf-8") as f:
        desert_data = json.load(f)
    with open(DATA_DIR / "mix_energetico.json", "r", encoding="utf-8") as f:
        energy_data = json.load(f)

    # I 5 topic come lista ordinabile. Ogni elemento ha la sua data di ultimo
    # aggiornamento; vengono renderizzati per updated_at DECRESCENTE
    # (il più recente in cima al feed).
    topics = [
        {
            "key": "bev",
            "updated_at": bev_data.get("updated_at", ""),
            "title": "Auto full electric immatricolate",
            "subtitle": "Nuove BEV registrate ogni mese in Italia. <strong>Barre verdi</strong>: numero immatricolazioni. <strong>Linea ruggine</strong>: quota di mercato.",
            "chart_html": chart_bev(bev_data),
            "source_html": 'Fonte: <a href="https://unrae.it/notizie" target="_blank" rel="noopener">UNRAE</a> · aggiornamento mensile',
        },
        {
            "key": "mobile",
            "updated_at": mob_data.get("updated_at", ""),
            "title": "Operatori telefonici mobili",
            "subtitle": "Classifica per quota di mercato sulle SIM <strong>Human</strong> (escluse M2M/IoT) nell'ultimo trimestre disponibile, con variazione rispetto a 12 mesi prima.",
            "chart_html": chart_mobile(mob_data),
            "source_html": 'Fonte: <a href="https://www.agcom.it/comunicazione/comunicati-stampa" target="_blank" rel="noopener">AGCOM — Osservatorio sulle Comunicazioni</a> · aggiornamento trimestrale',
        },
        {
            "key": "desert",
            "updated_at": desert_data.get("updated_at", ""),
            "title": "Desertificazione bancaria",
            "subtitle": "Numero totale di sportelli bancari aperti in Italia, a fine anno. La rete fisica si è quasi <strong>dimezzata in 15 anni</strong>: oltre 11mila sportelli chiusi dal picco del 2012, accelerazione durante la pandemia.",
            "chart_html": chart_desertification(desert_data),
            "source_html": 'Fonte: <a href="https://www.firstcisl.it/tag/osservatorio-desertificazione-bancaria/" target="_blank" rel="noopener">First CISL — Osservatorio sulla Desertificazione Bancaria</a> (su dati Banca d\'Italia / ISTAT) · aggiornamento annuale (fine gennaio)',
        },
        {
            "key": "payments",
            "updated_at": pay_data.get("updated_at", ""),
            "title": "Cashless vs contanti",
            "subtitle": "Quota dei consumi delle famiglie italiane regolata con strumenti elettronici (<strong>blu pieno</strong>) o in contante (<strong>oro tratteggiato</strong>). Il sorpasso è avvenuto nel 2024.",
            "chart_html": chart_payments(pay_data),
            "source_html": 'Fonte: <a href="https://www.osservatori.net/innovative-payments/" target="_blank" rel="noopener">Osservatorio Innovative Payments — Politecnico di Milano</a> · aggiornamento annuale (marzo)',
        },
        {
            "key": "energy",
            "updated_at": energy_data.get("updated_at", ""),
            "title": "Mix di generazione elettrica",
            "subtitle": "Composizione mensile della produzione elettrica nazionale (TWh) per fonte primaria. Si vede la <strong>stagionalità del solare</strong> (estate vs inverno) e la prevalenza del <strong>gas naturale</strong> tra le fossili.",
            "chart_html": chart_energy_mix(energy_data),
            "source_html": 'Fonte: <a href="https://transparency.entsoe.eu/" target="_blank" rel="noopener">ENTSO-E Transparency Platform</a> (dati Terna) · aggiornamento mensile',
        },
        {
            "key": "banks",
            "updated_at": banks_data.get("updated_at", ""),
            "title": "Banche e fintech",
            "subtitle": "Numero clienti delle principali banche italiane nell'ultimo anno disponibile, con la <strong>variazione percentuale anno su anno</strong>. Spicca la crescita di <strong>Revolut</strong> contro la sostanziale stabilità delle tradizionali.",
            "chart_html": chart_banks(banks_data),
            "source_html": 'Fonte: bilanci annuali e comunicati ufficiali · aggiornamento annuale (primavera, manuale)',
        },
    ]
    # Feed-style: il più recente in cima. A parità di data, ordine stabile.
    topics.sort(key=lambda t: t["updated_at"], reverse=True)

    topics_html = "\n\n".join(render_topic(t) for t in topics)
    updated_at = max(t["updated_at"] for t in topics) or "—"

    out = (TEMPLATE
           .replace("__TOPICS__", topics_html)
           .replace("__UPDATED_AT__", updated_at)
           .replace("__BUILD_DATE__", date.today().isoformat()))

    OUTPUT_HTML.write_text(out, encoding="utf-8")
    print(f"✓ Sito generato in {OUTPUT_HTML}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
