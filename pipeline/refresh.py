# -*- coding: utf-8 -*-
"""Denni refresh dat pro blog carousel Chlorito.

Rozdil proti Erice: dostupnost i cena se ctou primo z karet kategorii
(Chlorito je ma v HTML jako "Skladem"), takze neni potreba produktovy feed
ani API token. Refresh tedy bezi v Actions bez jakychkoli tajemstvi.

Vystup: a/<slug>.json se dvema sadami — "top" (pod prvni odstavec) a
"bottom" (za posledni odstavec). Kazda sada ma vlastni produkty, aby ctenar
dole nevidel to same co nahore.
"""
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "pipeline" / "config.json").read_text(encoding="utf-8"))
SHOP = CONFIG["shop_url"]
UA = {"User-Agent": "Mozilla/5.0 (compatible; chlorito-blog-carousel/1.0)"}


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read().decode("utf-8", "replace")


def slug_of(url):
    return url.split("?")[0].rstrip("/").rsplit("/", 1)[-1]


CARD_RE = re.compile(
    r'data-micro="product"[^>]*data-micro-product-id="(?P<pid>[^"]+)"[^>]*'
    r'data-micro-identifier="(?P<guid>[^"]+)".*?'
    r'href="(?P<href>[^"]+)"[^>]*class="image".*?'
    r'(?P<imgtag><img[^>]+>).*?'
    r'data-testid="productCardName">\s*(?P<name>[^<]+?)\s*</span>.*?'
    r'data-micro-price="(?P<price>[0-9.]+)"',
    re.S,
)


def real_img(imgtag):
    """Lazy-load karty maji v src placeholder a realny obrazek v data-src."""
    attrs = dict(re.findall(r'(data-src|src)="([^"]+)"', imgtag))
    for key in ("data-src", "src"):
        val = (attrs.get(key) or "").strip()
        if val and not val.startswith("data:"):
            return val
    return ""


NEDOSTUPNE = ("není skladem", "nedostupn", "vyprod", "na dotaz", "vypredan")


def in_stock(card_html):
    """Chlorito pise dostupnost primo do karty:
    <div class="availability"><span style="color:#009901">Skladem</span>…"""
    m = re.search(r'class="availability"(.{0,400}?)</div>', card_html, re.S)
    if not m:
        return False
    text = re.sub(r"<[^>]+>", " ", m.group(1)).replace("&nbsp;", " ").lower()
    if any(x in text for x in NEDOSTUPNE):
        return False
    return "skladem" in text


def single_product(path, html):
    """Clanky Chlorita odkazuji i na konkretni produkty. Takovy odkaz je
    nejsilnejsi signal relevance — redakce ten produkt sama doporucila."""
    if "Skladem" not in html:
        return []
    m = re.search(r"<h1[^>]*>\s*([^<]{3,120})", html)
    name = re.sub(r"\s+", " ", m.group(1)).strip() if m else ""
    m = re.search(r'data-micro-price="([0-9.]+)"', html)
    price = float(m.group(1)) if m else 0.0
    m = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html) or \
        re.search(r'data-micro-image="([^"]+)"', html)
    img = m.group(1) if m else ""
    if img.startswith("/"):
        img = SHOP + img
    if not name or not price or not img:
        return []
    slug = path.strip("/").split("/")[-1]
    m = re.search(r'data-micro-identifier="([^"]+)"', html)
    mp = re.search(r'data-micro-product-id="([^"]+)"', html)
    return [{"slug": slug, "code": m.group(1) if m else slug,
             "pid": mp.group(1) if mp else "", "name": name,
             "url": SHOP + path, "img": img, "price": price, "_direct": True}]


_CACHE = {}


def category_products(cat_path):
    """Kandidati z kategorie v poradi vypisu; kategorie se stahuje jen jednou.
    Kdyz cesta neni kategorie, zkusi se precist jako jeden produkt."""
    if cat_path in _CACHE:
        return _CACHE[cat_path]
    out, seen = [], set()
    for page in range(1, CONFIG["max_category_pages"] + 1):
        suffix = "" if page == 1 else f"strana-{page}/"
        try:
            html = fetch(SHOP + cat_path + suffix)
        except Exception:
            break
        if page == 1 and 'productCards' not in html:
            out = single_product(cat_path, html)
            break
        found = 0
        for m in CARD_RE.finditer(html):
            slug = slug_of(m.group("href"))
            if slug in seen:
                continue
            seen.add(slug)
            # dostupnost hledej v useku karty za cenou
            konec = html.find('data-micro="product"', m.end())
            karta = html[m.start():konec if konec > 0 else m.end() + 2000]
            if not in_stock(karta):
                continue
            img = real_img(m.group("imgtag"))
            if img.startswith("/"):
                img = SHOP + img
            href = m.group("href")
            out.append({
                "slug": slug,
                "code": m.group("guid"),
                # id produktu — timhle se na dekovaci strance paruje nakup
                "pid": m.group("pid"),
                "name": re.sub(r"\s+", " ", m.group("name")).strip(),
                "url": href if href.startswith("http") else SHOP + href,
                "img": img,
                "price": float(m.group("price")),
            })
            found += 1
        if found == 0 or f"strana-{page + 1}/" not in html:
            break
    _CACHE[cat_path] = out
    return out


def build_list(cat_paths, scores, potreba):
    picked, seen = [], set()
    for ci, cat in enumerate(cat_paths):
        for card in category_products(cat):
            if card["slug"] in seen:
                continue
            seen.add(card["slug"])
            picked.append(dict(card, _sales=scores.get(card["code"], 0),
                               _cat=ci, _direct=card.get("_direct", False)))
        if len(picked) >= potreba * 2 and ci == 0:
            break
    # produkt, ktery clanek sam doporucuje, patri na prvni misto
    picked.sort(key=lambda p: (not p["_direct"], -p["_sales"], p["_cat"]))
    return [{k: v for k, v in p.items() if not k.startswith("_")} for p in picked]


def main():
    scores_file = ROOT / "data" / "scores.json"
    scores = json.loads(scores_file.read_text(encoding="utf-8")) if scores_file.exists() else {}
    n = CONFIG["products_per_carousel"]
    potreba = n * CONFIG["positions"]

    fallback = build_list(CONFIG["fallback_categories"], scores, potreba)

    outdir = ROOT / "a"
    outdir.mkdir(exist_ok=True)
    for old in outdir.glob("*.json"):
        old.unlink()

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    hotovo = 0
    for article_path, spec in CONFIG["articles"].items():
        items = build_list(spec["categories"], scores, potreba)
        # dorovnani bestsellery, aby carousel nikdy neprorídl
        if len(items) < potreba:
            have = {p["url"] for p in items}
            for p in fallback:
                if len(items) >= potreba:
                    break
                if p["url"] not in have:
                    items.append(p)
                    have.add(p["url"])
        if len(items) < CONFIG["min_products"]:
            print(f"VAROVANI: {article_path} ma jen {len(items)} produktu", file=sys.stderr)
            continue
        # dole ukaz jine produkty nez nahore; kdyz jich neni dost, zopakuj od zacatku
        top = items[:n]
        bottom = items[n:potreba] if len(items) >= n + CONFIG["min_products"] else items[:n]
        slug = article_path.strip("/").split("/")[-1]
        (outdir / f"{slug}.json").write_text(
            json.dumps({"generated": generated, "top": top, "bottom": bottom},
                       ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        hotovo += 1

    (outdir / "_default.json").write_text(
        json.dumps({"generated": generated, "top": fallback[:n],
                    "bottom": fallback[n:potreba] or fallback[:n]},
                   ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (ROOT / "index.json").write_text(
        json.dumps({"generated": generated, "count": hotovo,
                    "fallback_enabled": CONFIG["fallback_enabled"],
                    "articles": sorted(CONFIG["articles"])}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(f"OK: {hotovo} clanku, fallback {len(fallback)} produktu skladem")


if __name__ == "__main__":
    main()
