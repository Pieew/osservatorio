"""
Fetch dati BEV (auto full electric) Italia da UNRAE.

Strategia (aggiornata al layout UNRAE 2026):
  1. Scarica la pagina dei comunicati autovetture (`/sala-stampa/autovetture/tag/immatricolazioni`)
  2. Splitta sui marker "Periodo di riferimento dei dati:" per isolare i singoli comunicati
  3. Per ogni comunicato Italia (filtra fuori "Europa"), estrae:
       - periodo (mese + anno)
       - quota di mercato BEV (%)
       - totale immatricolazioni del mese (dal titolo)
       - calcola le BEV assolute = totale × quota
  4. Prende il primo comunicato Italia con quota disponibile (= mese più recente)
  5. Appende al JSON se è un nuovo periodo

Vantaggio rispetto al PDF parsing: i dati sono nel testo HTML del comunicato,
nessun PDF da scaricare/parsare.

Se UNRAE cambia ancora il layout: rimani sotto controllo, lo script logga
chiaramente cosa ha trovato e cosa no, ed esce con codice di errore se
non riesce a estrarre.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "bev_italia.json"
UNRAE_URL = "https://unrae.it/sala-stampa/autovetture/tag/immatricolazioni"
USER_AGENT = "Mozilla/5.0 (compatible; OsservatorioBot/1.0; +github-actions)"
TIMEOUT = 30

MESI = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4,
    "maggio": 5, "giugno": 6, "luglio": 7, "agosto": 8,
    "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
}


def parse_comunicati(html: str) -> list[dict]:
    """Estrae lista di comunicati Italia dalla pagina UNRAE."""
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)

    # Salta menu di navigazione: comincia dal marker della lista comunicati.
    m = re.search(r"Stai filtrando per TAG:?\s*immatricolazioni", text, re.IGNORECASE)
    if m:
        text = text[m.end():]

    # Splitta sui marker di fine-comunicato. parts[i] contiene il testo del
    # comunicato (i+1)-esimo, preceduto dal "periodo" del comunicato i-esimo.
    parts = re.split(r"Periodo di riferimento dei dati:", text)

    risultati = []
    for i in range(len(parts) - 1):
        body = parts[i]
        # All'inizio di parts[i+1] c'è "mese anno" = periodo del comunicato i+1
        pm = re.match(r"\s*(\w+)\s+(\d{4})", parts[i + 1])
        if not pm:
            continue
        mese_nome = pm.group(1).lower()
        anno = int(pm.group(2))
        if mese_nome not in MESI:
            continue
        periodo = f"{anno}-{MESI[mese_nome]:02d}"

        # Per i record dal secondo in poi, c'è il "mese anno" del comunicato
        # precedente all'inizio del body: lo strippiamo.
        if i >= 1:
            body = re.sub(r"^\s*\w+\s+\d{4}", "", body)

        titolo = body[:300].strip()
        # Esclude comunicati riferiti al mercato europeo, non italiano
        if re.search(r"(mercato\s+(auto\s+)?europ|^\s*europa\s*:)", titolo, re.IGNORECASE):
            continue

        # Quota di mercato BEV
        quota_m = re.search(
            r"(?:elettriche pure|BEV)[^%]{0,80}(\d+[,\.]\d+)\s*%",
            body, re.IGNORECASE,
        )
        # Totale immatricolazioni del mese (numero italiano con separatore migliaia)
        tot_m = re.search(
            r"\b(\d{1,3}(?:\.\d{3}){1,2})\s+(?:nuove\s+)?"
            r"(?:immatricolazioni|autovetture|targhe|unità)",
            body, re.IGNORECASE,
        )

        quota = float(quota_m.group(1).replace(",", ".")) if quota_m else None
        totale = int(tot_m.group(1).replace(".", "")) if tot_m else None
        bev_assolute = round(totale * quota / 100) if (totale and quota) else None

        risultati.append({
            "period": periodo,
            "registrations": bev_assolute,
            "market_share_pct": quota,
            "_total_month": totale,  # utile per debug, non viene salvato
        })
    return risultati


def append_observation(new_obs: dict) -> bool:
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    existing = {o["period"] for o in data["observations"]}
    if new_obs["period"] in existing:
        print(f"  ⊝ periodo {new_obs['period']} già presente, skip.")
        return False

    # Rimuovi campi interni con underscore prima di salvare
    clean = {k: v for k, v in new_obs.items() if not k.startswith("_")}
    data["observations"].append(clean)
    data["observations"].sort(key=lambda o: o["period"])
    data["updated_at"] = date.today().isoformat()

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  ✓ aggiunto: {clean}")
    return True


def main() -> int:
    print("→ Scarico pagina comunicati UNRAE...")
    try:
        resp = requests.get(UNRAE_URL, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
        resp.raise_for_status()

        comunicati = parse_comunicati(resp.text)
        if not comunicati:
            print("  ✗ Nessun comunicato Italia trovato (layout cambiato?).")
            return 1

        # Prendiamo il primo comunicato con almeno la quota BEV
        validi = [c for c in comunicati if c["market_share_pct"] is not None]
        if not validi:
            print("  ✗ Nessun comunicato contiene la quota BEV.")
            return 1

        latest = validi[0]
        print(f"  Trovato: periodo={latest['period']} "
              f"quota_bev={latest['market_share_pct']}% "
              f"totale_mese={latest.get('_total_month')} "
              f"bev_calcolate={latest['registrations']}")

        append_observation(latest)
        return 0

    except requests.RequestException as e:
        print(f"  ✗ Errore di rete: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"  ✗ Errore imprevisto: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
