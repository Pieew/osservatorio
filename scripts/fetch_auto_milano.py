"""
Fetch dati parco auto provincia di Milano da ACI Autoritratto.

ACI pubblica l'Autoritratto a fine anno (novembre tipicamente) con i dati
del parco circolante al 31 dicembre dell'anno precedente.

Strategia:
  1. Scarica la pagina indice https://www.aci.it/.../open-data.html
  2. Trova il link al file "Autoritratto-YYYY-OD.zip" più recente
  3. Estrai l'anno dal nome del file
  4. Se è già nel JSON, esci
  5. Altrimenti scarica lo ZIP, trova il file Parco_veicolare_YYYY.ods
     (ricorsivamente nei sub-ZIP, la struttura varia anno per anno)
  6. Legge i 3 fogli per alimentazione × provincia:
       - AVBenz_Provincia (benzina pura)
       - AVGasolio_Prov (gasolio puro)
       - AVAltre_Provincia (GPL + metano + ibridi + elettrici)
  7. Estrae la riga MILANO da ciascuno
  8. Aggiunge l'osservazione al JSON

Nota: ACI a livello provinciale non disaggrega "altre" in sub-categorie
(ibrido vs elettrico vs GPL). Per quel dettaglio servirebbe la dashboard
interattiva opv.aci.it, di fatto non scrappabile.
"""
from __future__ import annotations

import json
import os
import re
import io
import sys
import tempfile
import zipfile
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "auto_milano.json"
INDEX_URL = "https://www.aci.it/laci/studi-e-ricerche/dati-e-statistiche/open-data.html"
USER_AGENT = "Mozilla/5.0 (compatible; OsservatorioBot/1.0; +github-actions)"
TIMEOUT = 120


def find_latest_autoritratto() -> tuple[int, str] | None:
    """Scrappa la pagina indice ACI e ritorna (anno, url) dell'Autoritratto più recente."""
    r = requests.get(INDEX_URL, headers={"User-Agent": USER_AGENT}, timeout=30)
    r.raise_for_status()
    # I link sono nella forma:
    #   https://aci.gov.it/app/uploads/YYYY/MM/Autoritratto-YYYY-OD.zip
    #   https://aci.gov.it/app/uploads/YYYY/MM/Autoritratto_YYYY_OD-1.zip
    pattern = r'(https?://aci\.gov\.it/[^"\']*Autoritratto[_\-]?(\d{4})[_\-][^"\']*\.zip)'
    matches = re.findall(pattern, r.text, re.IGNORECASE)
    if not matches:
        return None
    # Tieni il match con anno più alto
    latest = max(matches, key=lambda m: int(m[1]))
    return int(latest[1]), latest[0]


def find_parco_ods(zip_bytes: bytes, year: int, depth: int = 0) -> bytes | None:
    """Trova ricorsivamente il file Parco_veicolare_YYYY.ods (o variante) nello ZIP.

    Negli anni 2020-2023 il file ODS sta direttamente nel ZIP esterno.
    Nel 2019 e dal 2024 sta dentro un sub-ZIP. Va gestito uniformemente.
    """
    if depth > 3:
        return None
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))

    # Pattern preferiti (basename only, no path)
    preferred_patterns = [
        rf"^Parco_veicolare_{year}\.ods$",
        rf"^Autoritratto{year}_Parco[_\s]veicolare\.ods$",
    ]
    for name in zf.namelist():
        base = os.path.basename(name)
        for p in preferred_patterns:
            if re.match(p, base, re.IGNORECASE):
                return zf.open(name).read()

    # Fallback: qualsiasi ods con "parco" + "veicolare" nel basename ma
    # senza "vendite" o "mondo" (per evitare il file globale "Vendite nel Mondo")
    for name in zf.namelist():
        base = os.path.basename(name).lower()
        if (base.endswith(".ods") and "parco" in base and "veicolare" in base
                and "vendite" not in base and "mondo" not in base):
            return zf.open(name).read()

    # Scendi nei sub-zip
    for name in zf.namelist():
        if name.lower().endswith(".zip"):
            sub = zf.open(name).read()
            r = find_parco_ods(sub, year, depth + 1)
            if r:
                return r
    return None


def extract_milano_data(ods_bytes: bytes) -> dict[str, int] | None:
    """Estrae i 3 valori (benzina, gasolio, altre) per la provincia di Milano."""
    import pandas as pd
    with tempfile.NamedTemporaryFile(suffix=".ods", delete=False) as tmp:
        tmp.write(ods_bytes)
        path = tmp.name
    try:
        xl = pd.ExcelFile(path, engine="odf")
        sheets = xl.sheet_names
        benz = next((s for s in sheets if "Benz" in s and "Prov" in s), None)
        gaso = next((s for s in sheets if ("Gasolio" in s or "Gasol" in s)
                     and "Prov" in s and "Benz" not in s), None)
        altre = next((s for s in sheets if "Altre" in s and "Prov" in s), None)
        if not all([benz, gaso, altre]):
            print(f"  Fogli mancanti: benz={benz}, gaso={gaso}, altre={altre}", file=sys.stderr)
            return None

        res = {}
        for label, sheet in [("benzina", benz), ("gasolio", gaso), ("altre", altre)]:
            df = pd.read_excel(path, engine="odf", sheet_name=sheet, header=None)
            for i in range(len(df)):
                row_vals = df.iloc[i].tolist()
                # Cerca cella con valore esatto "MILANO" (per evitare false positive
                # come "MILANO COMUNE" o "MILANO MARITTIMA")
                if any(isinstance(v, str) and v.strip().upper() == "MILANO"
                       for v in row_vals):
                    import pandas as _pd
                    nums = [x for x in row_vals
                            if isinstance(x, (int, float)) and not _pd.isna(x)]
                    if nums:
                        res[label] = int(nums[-1])  # ultima colonna = totale
                    break

        return res if len(res) == 3 else None
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def main() -> int:
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    existing_years = {o["year"] for o in data["observations"]}

    print("→ Cerco l'Autoritratto più recente su ACI…")
    latest = find_latest_autoritratto()
    if not latest:
        print("Nessun link trovato. La pagina indice ACI potrebbe essere cambiata.", file=sys.stderr)
        return 1
    year, url = latest
    print(f"  Trovato: Autoritratto {year} → {url}")

    if year in existing_years:
        print(f"Anno {year} già presente nel JSON, niente da fare.")
        return 0

    print(f"→ Scarico ZIP per anno {year}…")
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    r.raise_for_status()
    print(f"  Scaricati {len(r.content) // 1024} KB")

    print("→ Estraggo il file Parco_veicolare ODS…")
    ods = find_parco_ods(r.content, year)
    if not ods:
        print("Non sono riuscito a trovare il file ODS atteso nello ZIP.", file=sys.stderr)
        return 1

    print("→ Estraggo i dati Milano provincia…")
    milano = extract_milano_data(ods)
    if not milano:
        print("Non sono riuscito a estrarre i dati Milano dai fogli.", file=sys.stderr)
        return 1

    new_obs = {
        "year": year,
        "benzina": milano["benzina"],
        "gasolio": milano["gasolio"],
        "altre": milano["altre"],
        "totale": milano["benzina"] + milano["gasolio"] + milano["altre"],
    }
    data["observations"].append(new_obs)
    data["observations"].sort(key=lambda o: o["year"])
    data["updated_at"] = date.today().isoformat()

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"✓ Aggiunta osservazione: {new_obs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
