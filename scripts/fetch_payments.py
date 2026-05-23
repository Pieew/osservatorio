"""
Fetch dati cashless vs contante Italia da Osservatorio Innovative Payments
(School of Management - Politecnico di Milano).

L'Osservatorio pubblica i dati annuali a marzo di ogni anno (es. i dati 2025
sono stati presentati il 12 marzo 2026). Lo script:
  1. Visita la pagina dei comunicati stampa dell'osservatorio
  2. Cerca l'ultimo comunicato annuale sui pagamenti digitali
  3. Estrae la quota % cashless e la quota % contante per l'anno appena chiuso
  4. Appende al JSON se è un nuovo anno

Lo script è "tollerante": gira ogni mese ma il dato cambia solo a marzo.
Negli altri mesi esce con successo senza modificare nulla.

NOTE: il sito osservatori.net mette i comunicati di anno in anno in pagine
diverse; lo scraping può rompersi. In quel caso il dato si aggiunge a mano
al JSON in data/pagamenti_italia.json — è un'operazione fatta una volta
l'anno (a marzo).
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "pagamenti_italia.json"

# Pagina indice dei comunicati dell'Osservatorio
OBS_BASE = "https://www.osservatori.net"
OBS_NEWS = "https://www.osservatori.net/it/eventi/comunicati-stampa"
USER_AGENT = "Mozilla/5.0 (compatible; OsservatorioBot/1.0; +github-actions)"
TIMEOUT = 30


def fetch_release_data() -> dict | None:
    """
    Cerca il comunicato più recente sui pagamenti digitali italiani e ne
    estrae anno + quote percentuali cashless/cash.

    Pattern testuali tipici:
      "Nel 2025 i pagamenti digitali ... 518 miliardi ... 45% dei consumi ...
       contante ... 38%"
    """
    # Prova prima la pagina indice
    try:
        resp = requests.get(OBS_NEWS, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    # Cerca link a comunicati che contengono "pagamenti digitali" nel testo
    candidates = []
    for a in soup.find_all("a", href=True):
        text = a.get_text(" ", strip=True).lower()
        if "pagamenti digitali" in text or "innovative payments" in text:
            candidates.append(urljoin(OBS_BASE, a["href"]))

    # Visita ciascun candidato e prova a estrarre i numeri
    for url in candidates[:5]:  # Limite a 5 per non spammare
        try:
            r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
            r.raise_for_status()
        except requests.RequestException:
            continue
        text = BeautifulSoup(r.text, "html.parser").get_text(" ", strip=True)

        # Cerca: "Nel <ANNO> ... <CASHLESS>% dei consumi ... contante ... <CASH>%"
        # I numeri possono variare; cerchiamo a finestra
        year_m = re.search(r"Nel\s+(20\d{2})[\s\S]{0,500}?(\d{2})\s*%\s+dei\s+consumi", text)
        cash_m = re.search(r"contante[\s\S]{0,200}?(\d{2})\s*%", text, re.IGNORECASE)
        value_m = re.search(r"(\d{2,4})\s*(?:mld|miliardi)\s+(?:di\s+)?euro", text, re.IGNORECASE)

        if year_m and cash_m:
            return {
                "year": int(year_m.group(1)),
                "cashless_pct": float(year_m.group(2)),
                "cash_pct": float(cash_m.group(1)),
                "cashless_value_bn_eur": int(value_m.group(1)) if value_m else None,
                "_source_url": url,
            }
    return None


def append_observation(new_obs: dict) -> bool:
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    existing_years = {o["year"] for o in data["observations"]}
    if new_obs["year"] in existing_years:
        print(f"  ⊝ anno {new_obs['year']} già presente, skip.")
        return False

    clean = {k: v for k, v in new_obs.items() if not k.startswith("_")}
    data["observations"].append(clean)
    data["observations"].sort(key=lambda o: o["year"])
    data["updated_at"] = date.today().isoformat()

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  ✓ aggiunto: {clean}")
    return True


def main() -> int:
    print("→ Cerco ultimo comunicato Osservatorio Innovative Payments...")
    try:
        obs = fetch_release_data()
        if not obs:
            print("  ⊝ Nessun nuovo comunicato annuale trovato (forse non è ancora marzo, o "
                  "la pagina è cambiata). Lo script ritenterà il prossimo mese.")
            return 0  # Non bloccante

        print(f"  Trovato: anno={obs['year']} cashless={obs['cashless_pct']}% "
              f"cash={obs['cash_pct']}% valore={obs.get('cashless_value_bn_eur')}mld "
              f"da {obs.get('_source_url')}")

        append_observation(obs)
        return 0
    except Exception as e:
        print(f"  ⊝ Errore (non bloccante): {e}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
