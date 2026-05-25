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

# Disattiva il template Plotly di default: evita di serializzare ~30KB di
# colorscale (Viridis, Plasma...) inutilizzati dentro OGNI chart.
pio.templates.default = "none"

ROOT = Path(__file__).resolve().parents[1]
REPO_URL = "https://github.com/Pieew/osservatorio"
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
    # Confronto a 5 anni: mostra meglio le dinamiche per banche tradizionali stabili.
    # Se la serie ha meno di 6 osservazioni, usiamo la più vecchia disponibile.
    prev_obs = obs[-6] if len(obs) >= 6 else obs[0]
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
            f"Variazione dal {prev_year}: %{{customdata}}<extra></extra>"
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


def chart_auto_milano(data: dict) -> str:
    """Stacked area annuale del parco auto in provincia di Milano per alimentazione.

    3 categorie aggregate (limite del dato ACI a livello provinciale):
      - Benzina (esclusi ibridi)
      - Gasolio (esclusi ibridi)
      - Altre (GPL + metano + ibrido + elettrico)
    """
    from datetime import datetime as _dt, timedelta
    obs = data.get("observations", [])
    if not obs:
        return ('<div style="padding:60px 20px;text-align:center;color:#8a7a55;'
                'font-style:italic;">Nessun dato disponibile.</div>')

    years_dt = [_dt(o["year"], 1, 1) for o in obs]
    first_year = years_dt[0].year
    last_year = years_dt[-1].year

    # Ordine stacked dal basso: benzina (stabile, base) → gasolio (in calo) → altre (in crescita)
    layers = [
        ("benzina",  "Benzina",                                "#a87544"),
        ("gasolio",  "Gasolio",                                "#5a5a5a"),
        ("altre",    "Altre (GPL, metano, ibrido, elettrico)", "#5d9b6a"),
    ]

    fig = go.Figure()
    for key, label, color in layers:
        values = [o.get(key, 0) / 1000 for o in obs]  # in migliaia
        fig.add_trace(go.Scatter(
            x=years_dt, y=values, name=label,
            stackgroup="one",
            mode="lines+markers",
            line=dict(color=color, width=0),
            marker=dict(size=6, color=color, line=dict(color=COLOR_BG, width=1.5)),
            fillcolor=color,
            cliponaxis=False,
            hovertemplate=f"<b>{label}</b><br>%{{x|%Y}}: %{{y:.0f}}k auto<extra></extra>",
        ))

    layout = common_layout()
    layout["margin"] = dict(l=60, r=60, t=30, b=50)
    layout["xaxis"] = dict(
        type="date", showgrid=False, linecolor=COLOR_GRID,
        tickformat="%Y",
        range=[_dt(first_year, 1, 1) - timedelta(days=120),
               _dt(last_year, 12, 31) + timedelta(days=60)],
    )
    layout["yaxis"] = dict(
        gridcolor=COLOR_GRID, zerolinecolor=COLOR_GRID, automargin=True,
        ticksuffix="k", rangemode="tozero",
    )
    layout["hovermode"] = "x unified"
    fig.update_layout(**layout)
    return pio.to_html(fig, include_plotlyjs=False, full_html=False, div_id="chart-auto-milano",
                       config=chart_config(static=True))


def chart_inquinamento(data: dict) -> str:
    """Line chart mensile della media PM2.5 in Pianura Padana lombarda.

    Mostra media delle 6 stazioni di background urbano, con la soglia OMS
    annuale (15 µg/m³) come riferimento di lettura.
    """
    from datetime import timedelta
    obs = data.get("observations", [])
    if not obs:
        return ('<div style="padding:60px 20px;text-align:center;color:#8a7a55;'
                'font-style:italic;">Nessun dato disponibile.</div>')

    obs = obs[-24:]
    periods = [datetime.strptime(o["period"], "%Y-%m").replace(day=15) for o in obs]
    values = [o["pm25_media"] for o in obs]

    COLOR_PM = "#a13e2a"   # terracotta scuro - "rosso preoccupante"
    THRESHOLD_OMS = data.get("threshold_oms_annuale", 15)

    fig = go.Figure()
    # Soglia OMS come banda di riferimento + linea
    fig.add_hrect(y0=0, y1=THRESHOLD_OMS, fillcolor="#7d9b5a", opacity=0.08, line_width=0)
    fig.add_hline(y=THRESHOLD_OMS, line_dash="dash", line_color="#5a7d3f", line_width=1.5,
                  annotation_text=f"Limite OMS (annuale): {THRESHOLD_OMS} µg/m³",
                  annotation_position="right",
                  annotation_font=dict(size=11, color="#5a7d3f"))
    # Linea principale
    fig.add_trace(go.Scatter(
        x=periods, y=values, name="PM2.5 medio",
        mode="lines+markers",
        line=dict(color=COLOR_PM, width=2.5),
        marker=dict(size=7, color=COLOR_PM, line=dict(color=COLOR_BG, width=1.5)),
        cliponaxis=False,
        hovertemplate="<b>%{x|%b %Y}</b><br>PM2.5: <b>%{y:.1f} µg/m³</b><extra></extra>",
    ))

    layout = common_layout()
    layout["margin"] = dict(l=60, r=160, t=30, b=50)  # margine destro extra per annotation
    layout["xaxis"] = dict(
        type="date", showgrid=False, linecolor=COLOR_GRID,
        range=[periods[0] - timedelta(days=20), periods[-1] + timedelta(days=20)],
    )
    layout["yaxis"] = dict(
        gridcolor=COLOR_GRID, zerolinecolor=COLOR_GRID, automargin=True,
        ticksuffix=" µg/m³", rangemode="tozero",
    )
    layout["showlegend"] = False
    fig.update_layout(**layout)
    return pio.to_html(fig, include_plotlyjs=False, full_html=False, div_id="chart-inquinamento",
                       config=chart_config(static=True))


TEMPLATE = """<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Osservatorio Italia — __N_TOPICS__ indicatori che raccontano il paese</title>
  <meta name="description" content="Monitoraggio automatico di __N_TOPICS__ indicatori italiani: auto elettriche, pagamenti, telecom, banche, energia, aria. Aggiornato di continuo da fonti pubbliche.">
  <meta property="og:title" content="Osservatorio Italia">
  <meta property="og:description" content="__N_TOPICS__ indicatori italiani aggiornati di continuo da fonti pubbliche.">
  <meta property="og:type" content="website">
  <meta property="og:url" content="__REPO_URL__">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,700&family=Geist:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #faf8f3;
      --bg-soft: #f3efe5;
      --fg: #1a1a1a;
      --fg-soft: #5a5651;
      --fg-mute: #8a847a;
      --rule: #d4cfc1;
      --rule-soft: #e8e2d2;
      /* Due famiglie di accent semantici per i topic */
      --accent-transizione: #1d6f42; /* mobilità, energia, ambiente */
      --accent-societa:     #2c4a7a; /* finanza, telecom, accesso */
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --bg: #16130f;
        --bg-soft: #1f1b16;
        --fg: #f0ebe0;
        --fg-soft: #a8a195;
        --fg-mute: #6e6a62;
        --rule: #322c25;
        --rule-soft: #28231d;
        --accent-transizione: #6cb88a;
        --accent-societa:     #7fa3d4;
      }
    }
    * { box-sizing: border-box; }
    html, body { margin: 0; padding: 0; background: var(--bg); color: var(--fg); }
    body { font-family: "Geist", system-ui, sans-serif; line-height: 1.5; -webkit-font-smoothing: antialiased; }
    a { color: inherit; }

    .wrap { max-width: 1080px; margin: 0 auto; padding: 64px 32px 96px; }

    /* ------- HEADER ------- */
    header.hero { border-bottom: 1px solid var(--rule); padding-bottom: 28px; margin-bottom: 24px; }
    .eyebrow { font-family: "Geist", sans-serif; text-transform: uppercase; letter-spacing: 0.18em; font-size: 11px; color: var(--fg-soft); margin: 0 0 12px; }
    h1 { font-family: "Fraunces", serif; font-weight: 500; font-size: clamp(38px, 5vw, 60px); line-height: 1.05; margin: 0 0 16px; letter-spacing: -0.01em; font-variation-settings: "opsz" 144; }
    h1 em { font-style: italic; font-weight: 400; color: var(--fg-soft); }
    .lede { font-family: "Fraunces", serif; font-size: 18px; line-height: 1.55; max-width: 62ch; color: var(--fg-soft); margin: 0; }
    .meta { display: flex; gap: 24px; flex-wrap: wrap; margin-top: 24px; font-size: 13px; color: var(--fg-soft); }
    .meta span strong { color: var(--fg); font-weight: 500; }

    /* ------- TOC / NAV ------- */
    nav.toc { margin: 0 0 72px; padding: 20px 0 0; font-size: 13px; }
    nav.toc ol { list-style: none; padding: 0; margin: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 4px 24px; counter-reset: tocnum; }
    nav.toc li { counter-increment: tocnum; border-top: 1px solid var(--rule-soft); padding: 10px 0; }
    nav.toc a { text-decoration: none; color: var(--fg); display: flex; align-items: baseline; gap: 10px; transition: color .15s; }
    nav.toc a::before { content: counter(tocnum, decimal-leading-zero); color: var(--fg-mute); font-variant-numeric: tabular-nums; font-size: 11px; min-width: 22px; }
    nav.toc a:hover { color: var(--accent-transizione); }
    nav.toc li[data-group="societa"] a:hover { color: var(--accent-societa); }
    nav.toc .toc-label { font-family: "Geist", sans-serif; letter-spacing: 0.16em; text-transform: uppercase; font-size: 10px; color: var(--fg-mute); margin: 0 0 10px; }

    /* ------- SECTION / CARD ------- */
    section.card { margin-bottom: 96px; scroll-margin-top: 20px; }
    section.card .cat { font-family: "Geist", sans-serif; text-transform: uppercase; letter-spacing: 0.18em; font-size: 10px; margin: 0 0 10px; }
    section.card[data-group="transizione"] .cat { color: var(--accent-transizione); }
    section.card[data-group="societa"]     .cat { color: var(--accent-societa); }
    section.card h2 { font-family: "Fraunces", serif; font-weight: 500; font-size: clamp(24px, 2.6vw, 32px); margin: 0 0 8px; letter-spacing: -0.005em; line-height: 1.15; }
    section.card .sub { color: var(--fg-soft); font-size: 14px; line-height: 1.55; margin: 0 0 24px; max-width: 64ch; }

    /* Headline KPI — la cifra-chiave prima del grafico */
    .headline { display: flex; align-items: baseline; gap: 18px; flex-wrap: wrap; margin: 0 0 18px; padding: 14px 0; border-top: 1px solid var(--rule-soft); border-bottom: 1px solid var(--rule-soft); }
    .headline .kpi { font-family: "Fraunces", serif; font-weight: 500; font-size: clamp(36px, 4.4vw, 52px); line-height: 1; letter-spacing: -0.02em; color: var(--fg); font-variant-numeric: tabular-nums; }
    .headline .kpi .unit { font-size: 0.42em; font-weight: 400; color: var(--fg-soft); margin-left: 6px; font-feature-settings: normal; letter-spacing: 0; }
    .headline .ctx { color: var(--fg-soft); font-size: 14px; line-height: 1.45; flex: 1 1 280px; }
    .headline .ctx .pos { color: var(--accent-transizione); font-weight: 500; }
    .headline .ctx .neg { color: #c0392b; font-weight: 500; }

    /* Citation / source — promosso a first-class */
    .citation { display: flex; gap: 16px; align-items: flex-start; margin: 0 0 24px; padding: 12px 14px; background: var(--bg-soft); border-left: 3px solid var(--rule); font-size: 12.5px; line-height: 1.5; }
    .citation .cite-label { font-family: "Geist", sans-serif; text-transform: uppercase; letter-spacing: 0.16em; font-size: 10px; color: var(--fg-mute); flex: 0 0 auto; padding-top: 2px; }
    .citation .cite-body { flex: 1; color: var(--fg-soft); }
    .citation .cite-body a { color: var(--fg); text-underline-offset: 2px; }
    .citation .cite-meta { color: var(--fg-mute); margin-left: 8px; }

    /* Chart container — min-height per evitare CLS al render Plotly */
    .chart-wrap { background: var(--bg); padding: 0; border-top: 1px solid var(--rule); border-bottom: 1px solid var(--rule); touch-action: pan-y; min-height: 420px; }
    .chart-wrap > div { min-height: 420px; }

    @media (pointer: coarse) {
      .chart-wrap .js-plotly-plot,
      .chart-wrap .js-plotly-plot * { pointer-events: none !important; }
    }

    /* Tabella dati collassabile sotto al chart */
    details.data-table { margin-top: 14px; font-size: 13px; }
    details.data-table summary { cursor: pointer; color: var(--fg-soft); font-family: "Geist", sans-serif; text-transform: uppercase; letter-spacing: 0.14em; font-size: 10.5px; padding: 6px 0; user-select: none; list-style: none; display: inline-flex; align-items: center; gap: 8px; }
    details.data-table summary::-webkit-details-marker { display: none; }
    details.data-table summary::before { content: "+"; display: inline-block; width: 14px; text-align: center; color: var(--fg-mute); font-weight: 400; }
    details.data-table[open] summary::before { content: "−"; }
    details.data-table summary:hover { color: var(--fg); }
    details.data-table table { width: 100%; border-collapse: collapse; margin-top: 12px; font-variant-numeric: tabular-nums; }
    details.data-table th, details.data-table td { text-align: right; padding: 6px 10px; border-bottom: 1px solid var(--rule-soft); }
    details.data-table th { font-weight: 500; color: var(--fg-mute); font-size: 11.5px; text-transform: uppercase; letter-spacing: 0.06em; }
    details.data-table td:first-child, details.data-table th:first-child { text-align: left; color: var(--fg-soft); }

    /* ------- FOOTER ------- */
    footer { margin-top: 96px; padding-top: 28px; border-top: 1px solid var(--rule); font-size: 12px; color: var(--fg-soft); display: flex; justify-content: space-between; flex-wrap: wrap; gap: 16px; }
    footer a { color: var(--fg); text-underline-offset: 2px; }

    @media (max-width: 640px) {
      .wrap { padding: 32px 16px 56px; }
      header.hero { margin-bottom: 16px; }
      nav.toc { margin-bottom: 48px; }
      nav.toc ol { grid-template-columns: 1fr; }
      h1 { font-size: 36px; }
      .lede { font-size: 16px; }
      section.card { margin-bottom: 64px; }
      .headline { gap: 10px; padding: 12px 0; }
      .chart-wrap { margin: 0 -16px; padding: 0; min-height: 360px; }
      .chart-wrap > div { min-height: 360px; }
      .citation { flex-direction: column; gap: 6px; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <header class="hero">
      <p class="eyebrow">Osservatorio Italia</p>
      <h1>Numeri pubblici <em>per leggere il paese</em></h1>
      <p class="lede">__N_TOPICS__ indicatori raccolti automaticamente da fonti pubbliche — UNRAE, AGCOM, Banca d'Italia, ARPA, ENTSO-E, ACI — per seguire come cambiano mobilità, consumi, finanza, energia e ambiente in Italia.</p>
      <div class="meta">
        <span>Ultimo dato disponibile: <strong>__UPDATED_AT__</strong></span>
        <span>Topic monitorati: <strong>__N_TOPICS__</strong></span>
        <span>Cadenze: <strong>mensile, trimestrale, annuale</strong></span>
      </div>
    </header>

    <nav class="toc" aria-label="Indice dei topic">
      <p class="toc-label">Indice</p>
      <ol>__TOC__</ol>
    </nav>

    <main>
    __TOPICS__
    </main>

    <footer>
      <span>Generato automaticamente · build __BUILD_DATE__</span>
      <span>Codice e dati: <a href="__REPO_URL__" target="_blank" rel="noopener">github.com/Pieew/osservatorio</a></span>
    </footer>
  </div>
</body>
</html>
"""


# ---------- Helpers per headline, citation, tabella dati ----------

MONTHS_IT = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
             "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]


def _fmt_int(n: float) -> str:
    """1234567 -> '1.234.567' (separatore italiano)."""
    return f"{int(round(n)):,}".replace(",", ".")


def _fmt_dec(n: float, digits: int = 1) -> str:
    """13.7 -> '13,7' (virgola decimale italiana, punto migliaia)."""
    s = f"{n:,.{digits}f}"  # es. "1,234.56"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def _fmt_period_it(period: str) -> str:
    """'2026-04' -> 'aprile 2026'. '2025-Q4' -> 'Q4 2025'. '2024' -> '2024'."""
    if "-Q" in period:
        y, q = period.split("-")
        return f"{q} {y}"
    if "-" in period:
        y, m = period.split("-")
        return f"{MONTHS_IT[int(m) - 1]} {y}"
    return period


def _delta_span(delta_pct: float, suffix: str = "") -> str:
    """Renderizza una variazione con classe positiva/negativa per il colore."""
    if delta_pct is None:
        return ""
    if delta_pct > 0:
        return f'<span class="pos">+{delta_pct:.0f}%{suffix}</span>'
    return f'<span class="neg">{delta_pct:.0f}%{suffix}</span>'


def headline_html(kpi: str, unit: str, context: str) -> str:
    """Blocco KPI prominente. `context` può contenere HTML inline."""
    unit_html = f'<span class="unit">{unit}</span>' if unit else ""
    return (f'<div class="headline">'
            f'<div class="kpi">{kpi}{unit_html}</div>'
            f'<div class="ctx">{context}</div>'
            f'</div>')


def citation_html(source: str, cadence: str, last_period: str) -> str:
    """Citazione editoriale al posto della footnote.

    `source` può contenere già <a>. `last_period` è 'aprile 2026' o '2025'.
    """
    meta_bits = [c for c in [cadence, f"ultimo dato: {last_period}" if last_period else None] if c]
    meta = " · ".join(meta_bits)
    return (f'<div class="citation">'
            f'<span class="cite-label">Fonte</span>'
            f'<span class="cite-body">{source}'
            f'<span class="cite-meta">— {meta}</span>'
            f'</span></div>')


def table_html(headers: list[str], rows: list[list[str]]) -> str:
    """Tabella collassabile 'Mostra i numeri' sotto al chart."""
    thead = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return (f'<details class="data-table">'
            f'<summary>Mostra i numeri</summary>'
            f'<table><thead><tr>{thead}</tr></thead><tbody>{body}</tbody></table>'
            f'</details>')


# ---------- Headline computation per ciascun topic ----------

def headline_bev(d: dict) -> str:
    obs = d["observations"]
    last = obs[-1]
    period = _fmt_period_it(last["period"])
    last_y, last_m = last["period"].split("-")
    yoy_period = f"{int(last_y) - 1}-{last_m}"
    yoy = next((o for o in obs if o["period"] == yoy_period), None)
    parts = [f"<b>{period}</b> · <b>{_fmt_dec(last['market_share_pct'])}%</b> di quota di mercato"]
    if yoy:
        delta = (last["registrations"] - yoy["registrations"]) / yoy["registrations"] * 100
        parts.append(f"{_delta_span(delta, ' YoY')} sulle immatricolazioni")
    return headline_html(_fmt_int(last["registrations"]), "BEV", " · ".join(parts))


def headline_mobile(d: dict) -> str:
    obs = d["observations"]
    last = obs[-1]
    ops = d["operators"]
    leader = max(ops, key=lambda o: last.get(o, 0))
    leader_share = last[leader]
    period = _fmt_period_it(last["period"])
    lo, hi = min(last[o] for o in ops), max(last[o] for o in ops)
    return headline_html(
        _fmt_dec(leader_share), "%",
        f"<b>{leader}</b> resta il primo operatore SIM Human nel <b>{period}</b>. "
        f"Quattro operatori si dividono il mercato in fasce strette: {lo:.0f}–{hi:.0f}%."
    )


def headline_desert(d: dict) -> str:
    obs = d["observations"]
    last = obs[-1]
    # picco storico per riferimento
    peak = max(obs, key=lambda o: o["sportelli"])
    delta = (last["sportelli"] - peak["sportelli"]) / peak["sportelli"] * 100
    ctx = (f"sportelli aperti a fine <b>{last['year']}</b>, "
           f"{_delta_span(delta)} dal picco di <b>{peak['year']}</b> ({_fmt_int(peak['sportelli'])}).")
    if last.get("comuni_senza_sportello"):
        ctx += f" <b>{_fmt_int(last['comuni_senza_sportello'])} comuni</b> oggi sono senza sportello bancario."
    return headline_html(_fmt_int(last["sportelli"]), "", ctx)


def headline_payments(d: dict) -> str:
    obs = d["observations"]
    last = obs[-1]
    return headline_html(
        f"{last['cashless_pct']:.0f}", "% cashless",
        f"dei consumi delle famiglie italiane nel <b>{last['year']}</b>. "
        f"Il contante è al <b>{last['cash_pct']:.0f}%</b>: il sorpasso è del 2024."
    )


def headline_pollution(d: dict) -> str:
    obs = d["observations"]
    last = obs[-1]
    period = _fmt_period_it(last["period"])
    threshold = d.get("threshold_oms_annuale", 15)
    value = last["pm25_media"]
    if value <= threshold:
        ratio_txt = f'<span class="pos">sotto la soglia annuale OMS</span> ({threshold} µg/m³)'
    else:
        x = value / threshold
        ratio_txt = f'<span class="neg">{_fmt_dec(x)}× la soglia annuale OMS</span> ({threshold} µg/m³)'
    return headline_html(
        _fmt_dec(value), "µg/m³",
        f"media PM2.5 di <b>{period}</b> su {last.get('stazioni_n', 6)} città lombarde — {ratio_txt}."
    )


def headline_auto_milano(d: dict) -> str:
    obs = d["observations"]
    last = obs[-1]
    first = obs[0]
    altre_growth = (last["altre"] - first["altre"]) / first["altre"] * 100
    gasolio_drop = (last["gasolio"] - first["gasolio"]) / first["gasolio"] * 100
    totale_m = last["totale"] / 1_000_000
    return headline_html(
        _fmt_dec(totale_m, 2), " M auto",
        f"totale provincia di Milano nel <b>{last['year']}</b>. "
        f"Dal {first['year']}: gasolio {_delta_span(gasolio_drop)}, "
        f"alimentazioni alternative {_delta_span(altre_growth)}."
    )


def headline_energy(d: dict) -> str:
    obs = d.get("observations", [])
    if not obs:
        return headline_html("—", "", "Dati in attesa della prima chiamata API a ENTSO-E. Il KPI apparirà al primo aggiornamento utile.")
    last = obs[-1]
    period = _fmt_period_it(last["period"])
    total = sum(v for k, v in last.items() if isinstance(v, (int, float)) and k != "year")
    return headline_html(_fmt_dec(total), " TWh", f"produzione elettrica nazionale di <b>{period}</b>.")


def headline_banks(d: dict) -> str:
    obs = d["observations"]
    banks = d["banks"]
    last = obs[-1]
    leader = max(banks, key=lambda b: last.get(b["name"], 0))
    leader_val = last[leader["name"]]
    revolut_first = obs[0].get("Revolut", 0) or 0.01
    revolut_last = last.get("Revolut", 0)
    rev_growth = (revolut_last - revolut_first) / revolut_first * 100
    return headline_html(
        _fmt_dec(leader_val), " M clienti",
        f"<b>{leader['name']}</b> capofila nel <b>{last['year']}</b>. "
        f"Sull'altro fronte, Revolut passa da {_fmt_dec(revolut_first, 2)}M ({obs[0]['year']}) "
        f"a {_fmt_dec(revolut_last)}M ({last['year']}): {_delta_span(rev_growth)}."
    )


# ---------- Tabelle dati per topic (opzionale, ultimi 12 valori) ----------

def table_bev(d: dict) -> str:
    obs = d["observations"][-12:]
    rows = [[_fmt_period_it(o["period"]), _fmt_int(o["registrations"]), f"{_fmt_dec(o['market_share_pct'])}%"]
            for o in reversed(obs)]
    return table_html(["Mese", "Immatricolazioni", "Market share"], rows)


def table_payments(d: dict) -> str:
    obs = d["observations"][-10:]
    rows = [[str(o["year"]), f"{o['cashless_pct']:.0f}%", f"{o['cash_pct']:.0f}%"]
            for o in reversed(obs)]
    return table_html(["Anno", "Cashless", "Contanti"], rows)


def table_desert(d: dict) -> str:
    obs = d["observations"][-10:]
    rows = [[str(o["year"]), _fmt_int(o["sportelli"])] for o in reversed(obs)]
    return table_html(["Anno", "Sportelli"], rows)


def table_pollution(d: dict) -> str:
    obs = d["observations"][-12:]
    rows = [[_fmt_period_it(o["period"]), f"{_fmt_dec(o['pm25_media'])} µg/m³"] for o in reversed(obs)]
    return table_html(["Mese", "PM2.5 media 6 città"], rows)


def render_topic(t: dict, index: int) -> str:
    """Renderizza una singola sezione topic con headline, citation, chart, tabella opzionale."""
    table = f"\n        {t['table_html']}" if t.get("table_html") else ""
    return f"""    <section class="card" id="{t['key']}" data-group="{t['group']}">
      <p class="cat">{t['category']}</p>
      <h2>{t['title']}</h2>
      <p class="sub">{t['subtitle']}</p>
      {t['headline_html']}
      {t['citation_html']}
      <div class="chart-wrap">
        {t['chart_html']}
      </div>{table}
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
    with open(DATA_DIR / "auto_milano.json", "r", encoding="utf-8") as f:
        auto_data = json.load(f)
    with open(DATA_DIR / "inquinamento_padana.json", "r", encoding="utf-8") as f:
        pollution_data = json.load(f)

    # Ultimo periodo "umano" per ogni dataset (per la citation block).
    def last_period_of(obs_list, key="period"):
        if not obs_list:
            return ""
        last = obs_list[-1]
        if key in last:
            return _fmt_period_it(last[key])
        if "year" in last:
            return str(last["year"])
        return ""

    # Ogni topic ha:
    #   key           – id ancora / nav
    #   group         – "transizione" | "societa"  → palette accent
    #   category      – eyebrow editoriale sopra al titolo
    #   updated_at    – per l'ordine feed-style (più recente in cima)
    #   title/subtitle
    #   chart_html, headline_html, citation_html, table_html?
    topics = [
        {
            "key": "bev",
            "group": "transizione",
            "category": "Mobilità · transizione",
            "updated_at": bev_data.get("updated_at", ""),
            "title": "Auto full electric immatricolate",
            "subtitle": "Nuove BEV registrate ogni mese in Italia. Barre: numero immatricolazioni; linea: quota di mercato sul totale del mese.",
            "chart_html": chart_bev(bev_data),
            "headline_html": headline_bev(bev_data),
            "citation_html": citation_html(
                '<a href="https://unrae.it/notizie" target="_blank" rel="noopener">UNRAE</a>',
                "aggiornamento mensile", last_period_of(bev_data["observations"]),
            ),
            "table_html": table_bev(bev_data),
        },
        {
            "key": "mobile",
            "group": "societa",
            "category": "Telecom · concorrenza",
            "updated_at": mob_data.get("updated_at", ""),
            "title": "Operatori telefonici mobili",
            "subtitle": "Quota di mercato sulle SIM Human (escluse M2M/IoT) nell'ultimo trimestre disponibile, con variazione rispetto allo stesso trimestre dell'anno prima.",
            "chart_html": chart_mobile(mob_data),
            "headline_html": headline_mobile(mob_data),
            "citation_html": citation_html(
                '<a href="https://www.agcom.it/comunicazione/comunicati-stampa" target="_blank" rel="noopener">AGCOM — Osservatorio sulle Comunicazioni</a>',
                "aggiornamento trimestrale", last_period_of(mob_data["observations"]),
            ),
        },
        {
            "key": "desert",
            "group": "societa",
            "category": "Accesso · servizi",
            "updated_at": desert_data.get("updated_at", ""),
            "title": "Desertificazione bancaria",
            "subtitle": "Numero totale di sportelli bancari aperti in Italia, a fine anno. Misura quanto la rete fisica si è ritirata dal picco del 2012.",
            "chart_html": chart_desertification(desert_data),
            "headline_html": headline_desert(desert_data),
            "citation_html": citation_html(
                '<a href="https://www.firstcisl.it/tag/osservatorio-desertificazione-bancaria/" target="_blank" rel="noopener">First CISL</a> (su dati Banca d\'Italia / ISTAT)',
                "aggiornamento annuale (fine gennaio)", str(desert_data["observations"][-1]["year"]),
            ),
            "table_html": table_desert(desert_data),
        },
        {
            "key": "payments",
            "group": "societa",
            "category": "Finanza · abitudini",
            "updated_at": pay_data.get("updated_at", ""),
            "title": "Cashless vs contanti",
            "subtitle": "Quota dei consumi delle famiglie italiane regolata con strumenti elettronici o in contante.",
            "chart_html": chart_payments(pay_data),
            "headline_html": headline_payments(pay_data),
            "citation_html": citation_html(
                '<a href="https://www.osservatori.net/innovative-payments/" target="_blank" rel="noopener">Osservatorio Innovative Payments — Politecnico di Milano</a>',
                "aggiornamento annuale (marzo)", str(pay_data["observations"][-1]["year"]),
            ),
            "table_html": table_payments(pay_data),
        },
        {
            "key": "energy",
            "group": "transizione",
            "category": "Energia · mix",
            "updated_at": energy_data.get("updated_at", ""),
            "title": "Mix di generazione elettrica",
            "subtitle": "Composizione mensile della produzione elettrica nazionale per fonte primaria. Si vede la stagionalità del solare e la prevalenza del gas tra le fossili.",
            "chart_html": chart_energy_mix(energy_data),
            "headline_html": headline_energy(energy_data),
            "citation_html": citation_html(
                '<a href="https://transparency.entsoe.eu/" target="_blank" rel="noopener">ENTSO-E Transparency Platform</a> (dati Terna)',
                "aggiornamento mensile", last_period_of(energy_data.get("observations", [])),
            ),
        },
        {
            "key": "pollution",
            "group": "transizione",
            "category": "Ambiente · aria",
            "updated_at": pollution_data.get("updated_at", ""),
            "title": "PM2.5 in Pianura Padana",
            "subtitle": "Media mensile di particolato fine PM2.5 nelle stazioni di background urbano di sei città lombarde (Milano, Brescia, Bergamo, Cremona, Pavia, Mantova).",
            "chart_html": chart_inquinamento(pollution_data),
            "headline_html": headline_pollution(pollution_data),
            "citation_html": citation_html(
                '<a href="https://www.dati.lombardia.it/Ambiente/Dati-sensori-aria/nicp-bhqi" target="_blank" rel="noopener">ARPA Lombardia</a> via dati.lombardia.it',
                "aggiornamento mensile", last_period_of(pollution_data["observations"]),
            ),
            "table_html": table_pollution(pollution_data),
        },
        {
            "key": "auto_milano",
            "group": "transizione",
            "category": "Mobilità · parco veicoli",
            "updated_at": auto_data.get("updated_at", ""),
            "title": "Auto in provincia di Milano",
            "subtitle": "Parco autovetture circolanti per tipo di alimentazione. Il totale è stabile ma la composizione si trasforma da un anno all'altro.",
            "chart_html": chart_auto_milano(auto_data),
            "headline_html": headline_auto_milano(auto_data),
            "citation_html": citation_html(
                '<a href="https://www.aci.it/laci/studi-e-ricerche/dati-e-statistiche/open-data.html" target="_blank" rel="noopener">ACI Autoritratto</a>',
                "aggiornamento annuale (autunno)", str(auto_data["observations"][-1]["year"]),
            ),
        },
        {
            "key": "banks",
            "group": "societa",
            "category": "Finanza · attori",
            "updated_at": banks_data.get("updated_at", ""),
            "title": "Banche e fintech",
            "subtitle": "Numero clienti delle principali banche italiane nell'ultimo anno disponibile, con la variazione rispetto a cinque anni prima.",
            "chart_html": chart_banks(banks_data),
            "headline_html": headline_banks(banks_data),
            "citation_html": citation_html(
                "bilanci annuali e comunicati ufficiali",
                "aggiornamento annuale (manuale)", str(banks_data["observations"][-1]["year"]),
            ),
        },
    ]
    # Feed-style: il più recente in cima. A parità di data, ordine stabile.
    topics.sort(key=lambda t: t["updated_at"], reverse=True)

    topics_html = "\n\n".join(render_topic(t, i) for i, t in enumerate(topics))

    # TOC: una voce per topic, mantenendo l'ordine già stabilito
    toc_items = "\n".join(
        f'      <li data-group="{t["group"]}"><a href="#{t["key"]}">{t["title"]}</a></li>'
        for t in topics
    )

    updated_at = max(t["updated_at"] for t in topics) or "—"
    n_topics = str(len(topics))

    out = (TEMPLATE
           .replace("__TOPICS__", topics_html)
           .replace("__TOC__", "\n" + toc_items + "\n    ")
           .replace("__N_TOPICS__", n_topics)
           .replace("__REPO_URL__", REPO_URL)
           .replace("__UPDATED_AT__", updated_at)
           .replace("__BUILD_DATE__", date.today().isoformat()))

    OUTPUT_HTML.write_text(out, encoding="utf-8")
    print(f"✓ Sito generato in {OUTPUT_HTML} ({len(topics)} topic)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
