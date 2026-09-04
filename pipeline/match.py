# -*- coding: utf-8 -*-
"""Namapuje vsechny blogove clanky Chlorita na kategorie e-shopu.

Signal = odkazy na kategorie, ktere redakce do clanku sama vlozila. Odkazy
spolecne vetsine clanku (menu, paticka, promo) se odfiltruji, zbydou jen ty
tematicke. Clanek bez tematickych odkazu zustane bez kategorii -> refresh.py
mu da bestsellery.

Pouziti: python match.py            (aktualizuje pipeline/config.json)
         python match.py --dry-run  (jen vypise, nic nemeni)
"""
import json
import re
import sys
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "pipeline" / "config.json"
CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
SHOP = CONFIG["shop_url"]
UA = {"User-Agent": "Mozilla/5.0 (compatible; ef-blog-carousel/1.0)"}

MAX_CATEGORIES = 3
# Odkaz, ktery se objevuje na vic nez tomto podilu clanku, je navigace, ne tema.
NAV_THRESHOLD = 0.30


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def blog_urls():
    """Chlorito ma sitemapu jako index odkazujici na gzipovane casti."""
    index = fetch(SHOP + "/sitemap.xml")
    casti = re.findall(r"<loc>([^<]+sitemap[^<]*\.xml(?:\.gz)?)</loc>", index) or [SHOP + "/sitemap.xml"]
    urls = set()
    for cast in casti:
        req = urllib.request.Request(cast, headers=UA)
        with urllib.request.urlopen(req, timeout=90) as r:
            raw = r.read()
        if cast.endswith(".gz") or raw[:2] == b"\x1f\x8b":
            raw = __import__("gzip").decompress(raw)
        text = raw.decode("utf-8", "replace")
        urls.update(re.findall(r"(https://www\.chlorito\.cz/blog/[^<\s]+/)", text))
    return sorted(urls)


def article_links(html):
    """Odkazy na kategorie z tela clanku (bez blogu, kariery a produktu)."""
    i = html.find('class="text"')
    j = html.find("news-item-detail-bottom")
    body = html[i:j if j > i else len(html)] if i > 0 else html
    out = []
    for href in re.findall(r'href="(?:https?://www\.chlorito\.cz)?(/[a-z0-9\-]+/)"', body):
        if "/blog/" in href or "/blog-rubrika/" in href:
            continue
        out.append(href)
    return out


def main():
    dry = "--dry-run" in sys.argv
    urls = blog_urls()
    print(f"Clanku v sitemape: {len(urls)}")

    per_article = {}
    for n, url in enumerate(urls, 1):
        try:
            per_article[url] = article_links(fetch(url))
        except Exception as exc:
            print(f"  chyba {url}: {exc}", file=sys.stderr)
            per_article[url] = []
        if n % 25 == 0:
            print(f"  stazeno {n}/{len(urls)}")

    # navigacni odkazy = ty, co jsou skoro vsude
    freq = Counter()
    for links in per_article.values():
        freq.update(set(links))
    nav = {href for href, c in freq.items() if c > len(urls) * NAV_THRESHOLD}
    print(f"Odfiltrovano jako navigace: {len(nav)} odkazu")

    articles = dict(CONFIG.get("articles", {}))
    rucne = set(articles)  # rucne overene mapovani neprepisuj
    novych, fallback = 0, 0
    for url, links in per_article.items():
        path = url.replace(SHOP, "")
        if path in rucne:
            continue
        # zachovej poradi vyskytu v clanku, vyhod navigaci a duplicity
        seen, cats = set(), []
        for href in links:
            if href in nav or href in seen:
                continue
            seen.add(href)
            cats.append(href)
        articles[path] = {"categories": cats[:MAX_CATEGORIES]}
        if cats:
            novych += 1
        else:
            fallback += 1

    print(f"Namapovano tematicky: {novych} | na bestsellery: {fallback} | rucne drzeno: {len(rucne)}")
    if dry:
        for p, spec in list(articles.items())[:15]:
            print("  ", p, "->", spec["categories"] or "(bestsellery)")
        return

    CONFIG["articles"] = articles
    CONFIG["fallback_enabled"] = True
    CONFIG_PATH.write_text(json.dumps(CONFIG, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Zapsano do {CONFIG_PATH}, celkem {len(articles)} clanku")


if __name__ == "__main__":
    main()
