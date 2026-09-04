/* Blog produktovy carousel — Chlorito
 * Nasazuje se jednim script tagem v paticce sablony (Navrhar sablon → HTML
 * editor → Zapati <BODY>), ideálne se SRI otiskem.
 *
 * Dva carousely v kazdem clanku:
 *   nahore  = pod prvnim odstavcem   -> item_list_id "blog_carousel_top"
 *   dole    = za poslednim odstavcem -> item_list_id "blog_carousel_bottom"
 * Kazdy ukazuje jine produkty a v GA4 se meri zvlast, takze jde porovnat,
 * ktere umisteni vydelava vic.
 *
 * Mereni: sdilene gtag na webu, ale KAZDY event musi mit send_to s merenim ID
 * GA4. Na webu je vedle GA4 nakonfigurovany i Google Ads (AW-…), takze bez
 * send_to jde event do Ads a do GA4 nedorazi. Overeno 4.9.2026 merenim
 * pozadavku na /g/collect: bez send_to 0 pozadavku, se send_to 1.
 */
(function () {
  "use strict";

  if (window.__ppcarLoaded) return;
  window.__ppcarLoaded = true;

  var BASE = "https://patrikpilous-dev.github.io/chlorito-blog-carousel";
  var GA_ID = "G-Y2XT91J533";
  var NADPIS = "Co se vám k tomu bude hodit";

  /* Badge na prvnich tri dlazdicich — stejne jako v upsell pluginu v kosiku,
     aby to zakaznik znal. Poradi odpovida poradi produktu (nejprodavanejsi). */
  var BADGES = [
    { text: "🔥 Výhodné", color: "#e8412a" },
    { text: "🐬 Chlorito doporučuje", color: "#1f6fc2" },
    { text: "🛒 Lidé právě nakupují", color: "#ef8c00" },
  ];

  if (!/^\/blog\/[^/]+\/$/.test(location.pathname)) return;
  var articleSlug = location.pathname.replace(/^\/blog\/|\/$/g, "");

  /* ---------- mereni ---------- */

  function ga4(eventName, pozice, items) {
    try {
      var params = {
        send_to: GA_ID,   // bez tohoto event skonci v Ads a do GA4 nedorazi
        item_list_id: "blog_carousel_" + pozice,
        item_list_name: "blog " + pozice + ": " + articleSlug,
        items: items.map(function (p, i) {
          return { item_id: String(p.code), item_name: p.name, price: p.price, index: i };
        }),
      };
      if (typeof window.gtag === "function") {
        window.gtag("event", eventName, params);
      } else {
        window.dataLayer = window.dataLayer || [];
        window.dataLayer.push({ ecommerce: null });
        window.dataLayer.push({ event: "blog_carousel_" + eventName, ecommerce: params });
      }
    } catch (e) { /* mereni nesmi rozbit stranku */ }
  }

  function markClick(product, pozice) {
    try {
      var log = JSON.parse(sessionStorage.getItem("ppcar_clicks") || "[]");
      log.push({ code: product.code, price: product.price, pozice: pozice,
                 article: articleSlug, ts: Date.now() });
      sessionStorage.setItem("ppcar_clicks", JSON.stringify(log.slice(-20)));
    } catch (e) { /* privatni rezim */ }
  }

  /* ---------- vykresleni ---------- */

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function safeUrl(u) {
    return /^https:\/\/www\.chlorito\.cz\//.test(u) ? u : "";
  }

  function formatPrice(p) {
    try {
      return new Intl.NumberFormat("cs-CZ", { style: "currency", currency: "CZK", maximumFractionDigits: 0 }).format(p);
    } catch (e) {
      return Math.round(p) + " Kč";
    }
  }

  var CSS = "" +
    ".ppcar{margin:32px 0 44px;font-family:inherit}" +
    ".ppcar h3{font-size:17px;margin:0 0 14px;font-weight:600}" +
    ".ppcar-wrap{position:relative}" +
    ".ppcar-track{display:flex;gap:16px;overflow-x:auto;scroll-snap-type:x mandatory;scroll-behavior:smooth;-webkit-overflow-scrolling:touch;padding:2px;scrollbar-width:none;-ms-overflow-style:none}" +
    ".ppcar-track::-webkit-scrollbar{display:none}" +
    ".ppcar-item{flex:0 0 46%;max-width:210px;scroll-snap-align:start;text-align:center}" +
    "@media(min-width:768px){.ppcar-item{flex-basis:23%}}" +
    ".ppcar .ppcar-item a,.ppcar .ppcar-item a:hover,.ppcar .ppcar-item a:focus{display:block;text-decoration:none !important;color:inherit}" +
    ".ppcar-imgwrap{position:relative}" +
    ".ppcar-item img{width:100%;height:auto;aspect-ratio:1/1;object-fit:contain;display:block;background:#fff}" +
    /* badge prevzaty z upsell pluginu v kosiku (.xs-badge) */
    ".ppcar-badge{position:absolute;top:8px;left:8px;color:#fff;font-size:12px;font-weight:700;padding:5px 10px;border-radius:6px;line-height:1.25;box-shadow:0 1px 5px rgba(0,0,0,.22)}" +
    ".ppcar-name{margin:10px 4px 4px;font-size:15px;line-height:1.4;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;min-height:2.8em}" +
    ".ppcar-price{font-size:16px;font-weight:600}" +
    ".ppcar-stock{font-size:14px;color:#009901;margin-top:4px}" +
    ".ppcar-btn{position:absolute;top:34%;transform:translateY(-50%);width:36px;height:36px;border:1px solid #ddd;border-radius:50%;background:#fff;cursor:pointer;font-size:16px;line-height:1;display:flex;align-items:center;justify-content:center;z-index:2;opacity:.92}" +
    ".ppcar-btn:hover{background:#000;color:#fff;border-color:#000}" +
    ".ppcar-prev{left:-8px}.ppcar-next{right:-8px}" +
    "@media(max-width:767px){.ppcar-btn{display:none}}";

  function vlozStyl() {
    if (document.getElementById("ppcar-style")) return;
    var s = document.createElement("style");
    s.id = "ppcar-style";
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  function odstavce() {
    var root = document.querySelector(".news-item-detail .text") ||
      document.querySelector(".news-item-detail");
    if (!root) return [];
    var out = [];
    var ps = root.querySelectorAll("p");
    for (var i = 0; i < ps.length; i++) {
      if (ps[i].querySelector("img")) continue;
      if (ps[i].textContent.trim().length >= 80) out.push(ps[i]);
    }
    return out;
  }

  function render(products, pozice, kotva, kam) {
    if (!products || !products.length || !kotva) return;
    vlozStyl();
    var sec = document.createElement("section");
    sec.className = "ppcar ppcar-" + pozice;
    var html = "<h3>" + esc(NADPIS) + "</h3><div class=\"ppcar-wrap\">" +
      "<button class=\"ppcar-btn ppcar-prev\" type=\"button\" aria-label=\"Předchozí\">&#10094;</button>" +
      "<div class=\"ppcar-track\">";
    var vykresleno = [];
    products.forEach(function (p) {
      var url = safeUrl(p.url), img = safeUrl(p.img);
      if (!url || !img) return;
      var i = vykresleno.length;
      vykresleno.push(p);
      var b = BADGES[i];
      var badge = b ? "<span class=\"ppcar-badge\" style=\"background:" + esc(b.color) +
        "\">" + esc(b.text) + "</span>" : "";
      html += "<div class=\"ppcar-item\"><a href=\"" + esc(url) + "\" data-i=\"" + i + "\">" +
        "<div class=\"ppcar-imgwrap\">" + badge +
        "<img loading=\"lazy\" src=\"" + esc(img) + "\" alt=\"" + esc(p.name) + "\"></div>" +
        "<div class=\"ppcar-name\">" + esc(p.name) + "</div>" +
        "<div class=\"ppcar-price\">" + esc(formatPrice(p.price)) + "</div>" +
        "<div class=\"ppcar-stock\">Skladem</div></a></div>";
    });
    if (!vykresleno.length) return;
    html += "</div><button class=\"ppcar-btn ppcar-next\" type=\"button\" aria-label=\"Další\">&#10095;</button></div>";
    sec.innerHTML = html;

    if (kam === "po") kotva.parentNode.insertBefore(sec, kotva.nextSibling);
    else kotva.parentNode.appendChild(sec);

    var track = sec.querySelector(".ppcar-track");
    sec.querySelector(".ppcar-prev").addEventListener("click", function () {
      track.scrollBy({ left: -track.clientWidth, behavior: "smooth" });
    });
    sec.querySelector(".ppcar-next").addEventListener("click", function () {
      track.scrollBy({ left: track.clientWidth, behavior: "smooth" });
    });
    sec.addEventListener("click", function (e) {
      var a = e.target.closest("a[data-i]");
      if (!a) return;
      var p = vykresleno[+a.getAttribute("data-i")];
      ga4("select_item", pozice, [p]);
      markClick(p, pozice);
    });

    if ("IntersectionObserver" in window) {
      var videno = false;
      new IntersectionObserver(function (entries, obs) {
        entries.forEach(function (en) {
          if (en.isIntersecting && !videno) {
            videno = true;
            ga4("view_item_list", pozice, vykresleno);
            obs.disconnect();
          }
        });
      }, { threshold: 0.3 }).observe(sec);
    } else {
      ga4("view_item_list", pozice, vykresleno);
    }
  }

  function load(name) {
    return fetch(BASE + "/a/" + name + ".json").then(function (r) {
      return r.ok ? r.json() : null;
    });
  }

  function init() {
    var ps = odstavce();
    if (!ps.length) return;
    load(articleSlug)
      .then(function (d) { return d || load("_default"); })
      .then(function (d) {
        if (!d) return;
        render(d.top, "top", ps[0], "po");
        render(d.bottom, "bottom", ps[ps.length - 1], "po");
      })
      .catch(function () { /* carousel je nice-to-have */ });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
