"""
Fetch dati mix energetico Italia da ENTSO-E Transparency Platform API.

Endpoint: Actual Generation per Type (documentType=A75, processType=A16)
Bidding zone Italia: 10YIT-GRTN-----B

Auth: API token via env var ENTSOE_API_TOKEN (registrazione gratuita
necessaria su https://transparency.entsoe.eu + email di richiesta a
transparency@entsoe.eu).

Strategia:
  1. Leggi il JSON corrente per scoprire l'ultimo mese già presente.
  2. Calcola il range da scaricare: dal mese dopo l'ultimo già salvato
     fino al mese SCORSO (il mese corrente non è ancora completo).
     Se il JSON è vuoto, fai backfill degli ultimi 24 mesi.
  3. ENTSO-E permette query massimo 1 anno alla volta per A75 → chunko
     in finestre annuali.
  4. Parse XML: per ogni TimeSeries (= una fonte = un PSR_TYPE),
     somma i MW orari ottenendo MWh, raggruppato per mese.
  5. Aggrega le ~15 fonti ENTSO-E in 6 categorie narrative:
     gas / solare / idro / eolico / altre_rinnovabili / altre_fossili
  6. Converte MWh in TWh (÷ 1e6) e arrotonda.
  7. Aggiorna il JSON SOLO se i dati sono effettivamente nuovi.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

import requests

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "mix_energetico.json"
API_URL = "https://web-api.tp.entsoe.eu/api"
ITALY_DOMAIN = "10YIT-GRTN-----B"
USER_AGENT = "Mozilla/5.0 (compatible; OsservatorioBot/1.0; +github-actions)"
TIMEOUT = 120

# PSR_TYPE → categoria narrativa (vedi codici ENTSO-E)
PSR_TO_CATEGORY = {
    "B01": "altre_rinnovabili",   # Biomass
    "B02": "altre_fossili",        # Fossil Brown coal/Lignite
    "B03": "altre_fossili",        # Fossil Coal-derived gas
    "B04": "gas",                  # Fossil Gas (la voce principale per Italia)
    "B05": "altre_fossili",        # Fossil Hard coal
    "B06": "altre_fossili",        # Fossil Oil
    "B07": "altre_fossili",        # Fossil Oil shale
    "B08": "altre_fossili",        # Fossil Peat
    "B09": "altre_rinnovabili",    # Geothermal
    # B10 (Hydro Pumped Storage) escluso: è accumulo, non generazione primaria
    "B11": "idro",                 # Hydro Run-of-river and poundage
    "B12": "idro",                 # Hydro Water Reservoir
    "B14": "altre_fossili",        # Nuclear (Italia non ha; cautelativamente non rinnovabile)
    "B15": "altre_rinnovabili",    # Other renewable
    "B16": "solare",               # Solar
    "B17": "altre_rinnovabili",    # Waste
    "B18": "eolico",               # Wind Offshore
    "B19": "eolico",               # Wind Onshore
    "B20": "altre_fossili",        # Other
}
CATEGORIES = ["gas", "solare", "idro", "eolico", "altre_rinnovabili", "altre_fossili"]

# Namespace XML usato da ENTSO-E
NS = {"ns": "urn:iec62325.351:tc57wg16:451-6:generationloaddocument:3:0"}


def fmt_period(dt: datetime) -> str:
    """ENTSO-E vuole il formato YYYYMMDDHHMM."""
    return dt.strftime("%Y%m%d%H%M")


def fetch_year(year: int, token: str) -> dict[str, dict[str, float]]:
    """Scarica un anno intero di dati. Ritorna {YYYY-MM: {categoria: MWh}}."""
    start = datetime(year, 1, 1)
    end = datetime(year + 1, 1, 1)
    params = {
        "documentType": "A75",
        "processType": "A16",
        "in_Domain": ITALY_DOMAIN,
        "periodStart": fmt_period(start),
        "periodEnd": fmt_period(end),
        "securityToken": token,
    }
    print(f"  → richiedo dati anno {year}…")
    r = requests.get(API_URL, params=params,
                     headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    if r.status_code != 200:
        print(f"  ERRORE: API HTTP {r.status_code}: {r.text[:300]}", file=sys.stderr)
        return {}
    return parse_response(r.text)


def parse_response(xml_text: str) -> dict[str, dict[str, float]]:
    """Parse XML ENTSO-E.

    Struttura:
      GL_MarketDocument
        TimeSeries (uno per ciascun PSR_TYPE)
          MktPSRType/psrType (es. "B16")
          Period
            timeInterval/start, end
            resolution (es. "PT60M" = 60 minuti)
            Point (quantity in MW per ogni intervallo)

    Ritorna: {"YYYY-MM": {"gas": MWh, "solare": MWh, ...}}
    """
    out: dict[str, dict[str, float]] = {}
    root = ET.fromstring(xml_text)

    for ts in root.findall("ns:TimeSeries", NS):
        psr_el = ts.find("ns:MktPSRType/ns:psrType", NS)
        if psr_el is None:
            continue
        psr = psr_el.text
        category = PSR_TO_CATEGORY.get(psr)
        if not category:
            continue

        for period in ts.findall("ns:Period", NS):
            start_el = period.find("ns:timeInterval/ns:start", NS)
            res_el = period.find("ns:resolution", NS)
            if start_el is None or res_el is None:
                continue
            start_dt = datetime.strptime(start_el.text, "%Y-%m-%dT%H:%MZ")
            res = res_el.text  # es. "PT60M", "PT15M"
            res_minutes = int(res.replace("PT", "").replace("M", "")) if "M" in res else 60
            hours_per_point = res_minutes / 60.0

            for point in period.findall("ns:Point", NS):
                pos_el = point.find("ns:position", NS)
                qty_el = point.find("ns:quantity", NS)
                if pos_el is None or qty_el is None:
                    continue
                pos = int(pos_el.text)
                quantity = float(qty_el.text)  # MW
                # Il punto a posizione N copre l'intervallo (N-1) → N
                point_dt = start_dt + timedelta(minutes=(pos - 1) * res_minutes)
                month_key = point_dt.strftime("%Y-%m")
                # MWh = MW * ore intervallo
                mwh = quantity * hours_per_point
                if month_key not in out:
                    out[month_key] = {c: 0.0 for c in CATEGORIES}
                out[month_key][category] += mwh

    return out


def mwh_to_twh(d: dict[str, float]) -> dict[str, float]:
    return {k: round(v / 1_000_000, 2) for k, v in d.items()}


def main() -> int:
    token = os.environ.get("ENTSOE_API_TOKEN")
    if not token:
        print("ENTSOE_API_TOKEN non impostato. Skip (probabilmente API key non ancora attiva).")
        return 0

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Cosa abbiamo già?
    existing = {o["period"] for o in data.get("observations", [])}
    last_month = max(existing) if existing else None

    # Cosa scaricare: dal mese dopo l'ultimo presente al mese SCORSO incluso
    today = date.today()
    end_target = date(today.year, today.month, 1) - timedelta(days=1)  # ultimo giorno mese scorso
    end_month = end_target.strftime("%Y-%m")

    if last_month and last_month >= end_month:
        print(f"Già aggiornato fino a {last_month}, niente da fare.")
        return 0

    # Backfill iniziale: 24 mesi indietro se JSON vuoto
    if not last_month:
        start_target = date(today.year - 2, today.month, 1)
    else:
        ly, lm = map(int, last_month.split("-"))
        # mese successivo all'ultimo presente
        next_m = lm + 1
        next_y = ly
        if next_m > 12:
            next_m = 1
            next_y += 1
        start_target = date(next_y, next_m, 1)

    print(f"Scarico da {start_target.strftime('%Y-%m')} a {end_month}")

    # Anni da chiedere (1 chiamata per anno)
    years = list(range(start_target.year, end_target.year + 1))
    all_months: dict[str, dict[str, float]] = {}
    for y in years:
        data_y = fetch_year(y, token)
        # Filtra solo i mesi nel range richiesto
        for month, vals in data_y.items():
            my_dt = datetime.strptime(month, "%Y-%m").date()
            if start_target.replace(day=1) <= my_dt.replace(day=1) <= end_target.replace(day=1):
                all_months[month] = vals

    if not all_months:
        print("Nessun dato nuovo dall'API.")
        return 0

    # Costruisci nuove osservazioni
    new_observations = []
    for month in sorted(all_months):
        if month in existing:
            continue
        twh = mwh_to_twh(all_months[month])
        new_observations.append({"period": month, **twh})

    if not new_observations:
        print("Nessun mese nuovo da aggiungere.")
        return 0

    # Aggiungi al JSON e ordina
    data["observations"].extend(new_observations)
    data["observations"].sort(key=lambda o: o["period"])
    data["updated_at"] = date.today().isoformat()

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"✓ Aggiunti {len(new_observations)} mesi: "
          f"{new_observations[0]['period']} → {new_observations[-1]['period']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
