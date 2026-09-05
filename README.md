# Chlorito — produktový carousel na blogu

Dva carousely v každém blogovém článku chlorito.cz, měřené v GA4 zvlášť.
Metodika: skill `blog-produktovy-carousel` v `~/.claude/skills`.

## Jak to funguje

- **carousel.js** — jediný script tag v patičce šablony (Návrhář šablon → HTML
  editor → Zápatí `<BODY>`). Na URL `/blog/<slug>/` stáhne `a/<slug>.json`
  a vykreslí dva carousely:
  - **top** pod první odstavec, `item_list_id: blog_carousel_top`
  - **bottom** za poslední odstavec, `item_list_id: blog_carousel_bottom`

  Každý ukazuje jiné produkty, takže čtenář dole nevidí totéž co nahoře.
- **a/\<slug\>.json** — generuje `pipeline/refresh.py` denně přes GitHub Actions.
  Kandidáti z kategorií podle `pipeline/config.json`, jen produkty **skladem**
  (čte se dostupnost přímo z karet kategorií), řazení podle prodejnosti.
- **data/scores.json** — prodané kusy za 30 dní, `pipeline/scores_from_api.py`
  ze Shoptet API (jen GET). Klíč je `productGuid`, stejný identifikátor mají
  karty v kategoriích (`data-micro-identifier`).

## Odlišnosti proti Erice

| | Erika | Chlorito |
|---|---|---|
| Dostupnost | z XML feedu | z karet kategorií (feed je zvenčí 403) |
| Prodejnost | ruční CSV export | Shoptet API, automaticky |
| Okno prodejnosti | 90 dní | **30 dní** (rychlá reakce na sezónu) |
| Carouselů na článek | 1 | **2**, měřené odděleně |
| Mapování | 37 % tematicky | **94 %** (95 ze 101 článků) |

Články odkazují i na konkrétní produkty, ne jen kategorie. Takový produkt se
bere jako nejsilnější signál relevance a řadí se na první místo.

## Aktualizace prodejnosti

```bash
python pipeline/scores_from_api.py 30
```
Token je v uživatelské proměnné `SHOPTET_CHLORITO` a **nesmí se dostat do
repozitáře**. Proto tenhle krok neběží v Actions; denní refresh dat token
nepotřebuje, čte jen veřejné stránky kategorií.

## Atribuce tržeb (thankyou.js)

`carousel.js` si při kliku uloží do `sessionStorage` (`ppcar_clicks`) id produktu,
název, cenu a pozici (top/bottom). Na děkovací stránce běží `thankyou.js`, spáruje
zakoupené položky (`shoptet.order.content[]`) s těmi kliknutými a pošle do GA4
událost **`blog_carousel_purchase`** se skutečnou tržbou, zvlášť pro každou pozici.

Proč to takhle: Shoptet posílá vlastní `purchase` a naše `item_list_id` v něm není,
takže GA4 by tržbu k seznamu nepřiřadilo samo.

- Párování: primárně `pid` (= `data-micro-identifier`… pozor, `pid` je
  `data-micro-product-id`, shoduje se s `order.content[].id`), záloha normalizovaný název.
- Okno: klik starší než 24 h se nepočítá. Po odeslání se `ppcar_clicks` maže.
- Vyhodnocení v GA4: událost `blog_carousel_purchase`, parametr `item_list_id`
  (`blog_carousel_top` / `blog_carousel_bottom`), metrika `value`.

## Nasazení

1. `carousel.js` → šablona, Zápatí `<BODY>`, se SRI otiskem.
2. `thankyou.js` → šablona, záložka **Dokončená objednávka**, se SRI otiskem.

Měřicí ID GA4 je `G-Y2XT91J533` a je v obou skriptech natvrdo. Každá událost musí
mít `send_to` — bez něj skončí v Google Ads a do GA4 nedorazí.

Otisk: `curl -s <url carousel.js> | python -c "import sys,hashlib,base64;print('sha384-'+base64.b64encode(hashlib.sha384(sys.stdin.buffer.read()).digest()).decode())"`

**Pozor:** při každé změně `carousel.js` se musí v šabloně vyměnit i otisk,
jinak se carousel přestane zobrazovat. Denní aktualizace dat se SRI netýká.

## Náhled

https://patrikpilous-dev.github.io/chlorito-blog-carousel/preview.html
