# -*- coding: utf-8 -*-
"""Prodejnost produktu za poslednich N dni ze Shoptet API (jen GET, read-only).

Vysledek: data/scores.json = { "<productGuid>": prodane_kusy }.
Klicem je GUID produktu — stejny identifikator maji karty v kategoriich
(data-micro-identifier), takze podle nej jde spolehlive parovat.

Spousti se lokalne (token je v uzivatelske promenne SHOPTET_CHLORITO,
nikdy se nesmi dostat do repozitare). Vysledek se commitne.

Pouziti: python scores_from_api.py [pocet_dni]
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "pipeline" / "config.json").read_text(encoding="utf-8"))
API = "https://api.myshoptet.com"
TOKEN = os.environ.get("SHOPTET_CHLORITO")
# stavy, ktere se nepocitaji do prodejnosti
STORNO = ("storn", "vrácen", "vracen", "nevyzved")


def call(path):
    req = urllib.request.Request(API + path, headers={
        "Shoptet-Private-API-Token": TOKEN,
        "User-Agent": "chlorito-blog-carousel/1.0",
    })
    for pokus in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429:          # rate limit
                time.sleep(5 * (pokus + 1))
                continue
            raise
    raise RuntimeError("API neodpovida: " + path)


def main():
    if not TOKEN:
        sys.exit("Chybi promenna SHOPTET_CHLORITO s API tokenem.")
    dni = int(sys.argv[1]) if len(sys.argv) > 1 else CONFIG["sales_window_days"]
    od = (datetime.now(timezone.utc) - timedelta(days=dni)).strftime("%Y-%m-%dT00:00:00%z")
    od = urllib.parse.quote(od or "", safe="")

    kody = []
    page = 1
    while True:
        d = call(f"/api/orders?creationTimeFrom={od}&page={page}&itemsPerPage=100")
        objednavky = d["data"]["orders"]
        for o in objednavky:
            stav = (o.get("status", {}) or {}).get("name", "").lower()
            if any(s in stav for s in STORNO):
                continue
            kody.append(o["code"])
        pag = d["data"]["paginator"]
        print(f"  stranka {page}/{pag['pageCount']}, objednavek {len(kody)}")
        if page >= pag["pageCount"]:
            break
        page += 1

    print(f"Objednavek k projeti: {len(kody)} (okno {dni} dni)")
    prodeje = Counter()
    for i, kod in enumerate(kody, 1):
        try:
            det = call(f"/api/orders/{kod}")
        except Exception as exc:
            print(f"  preskoceno {kod}: {exc}", file=sys.stderr)
            continue
        for it in det["data"]["order"].get("items", []):
            # doprava a platba productGuid nemaji, ty preskakujeme
            guid = it.get("productGuid")
            if not guid or it.get("itemType") != "product":
                continue
            try:
                prodeje[guid] += int(float(it.get("amount") or 1))
            except (TypeError, ValueError):
                prodeje[guid] += 1
        if i % 100 == 0:
            print(f"  zpracovano {i}/{len(kody)}")

    out = ROOT / "data"
    out.mkdir(exist_ok=True)
    (out / "scores.json").write_text(json.dumps(dict(prodeje), ensure_ascii=False), encoding="utf-8")
    (out / "scores-meta.json").write_text(json.dumps({
        "okno_dni": dni,
        "objednavek": len(kody),
        "produktu": len(prodeje),
        "aktualizovano": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }, ensure_ascii=False), encoding="utf-8")
    print(f"OK: {len(prodeje)} produktu -> data/scores.json")


if __name__ == "__main__":
    main()
