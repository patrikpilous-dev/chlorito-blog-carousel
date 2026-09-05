/* Atribuce trzeb blogovemu carouselu — Chlorito
 *
 * Bezi jen na dekovaci strance (Navrhar sablon → HTML editor → zalozka
 * "Dokoncena objednavka"). Vezme produkty, na ktere clovek behem navstevy
 * kliknul v carouselu (ulozene v sessionStorage skriptem carousel.js),
 * spari je s tim, co skutecne koupil, a posle do GA4 udalost
 * "blog_carousel_purchase" s realnou trzbou — zvlast pro carousel nahore
 * a dole.
 *
 * Proc to musi byt takhle: Shoptet posila vlastni purchase event a nase
 * item_list_id v nem neni, takze GA4 by trzbu k seznamu nepriradilo samo.
 *
 * Parovani: primarne podle id produktu (order.content[].id = pid z karty
 * v kategorii), zaloha podle normalizovaneho nazvu.
 */
(function () {
  "use strict";

  if (window.__ppcarThankYou) return;
  window.__ppcarThankYou = true;

  var GA_ID = "G-Y2XT91J533";
  var OKNO_HODIN = 24;   // klik starsi nez tohle uz k objednavce nepocitame

  function objednavka() {
    try {
      if (typeof window.getShoptetDataLayer === "function") {
        var o = window.getShoptetDataLayer("order");
        if (o && o.content) return o;
      }
    } catch (e) { /* helper nemusi existovat */ }
    try {
      var dl = window.dataLayer || [];
      for (var i = 0; i < dl.length; i++) {
        var s = dl[i] && dl[i].shoptet;
        if (s && s.order && s.order.content) return s.order;
      }
    } catch (e) { /* nic */ }
    return null;
  }

  /* Nazev z objednavky a z karty se muze lisit diakritikou nebo mezerami. */
  function norm(s) {
    var t = String(s == null ? "" : s).toLowerCase();
    try { t = t.normalize("NFD").replace(/[̀-ͯ]/g, ""); } catch (e) { /* stare prohlizece */ }
    return t.replace(/\s+/g, " ").trim();
  }

  function posli(pozice, polozky, order) {
    var hodnota = 0;
    polozky.forEach(function (p) { hodnota += p.price * p.quantity; });
    if (!hodnota) return;
    var params = {
      send_to: GA_ID,      // bez tohoto by event skoncil v Ads, ne v GA4
      item_list_id: "blog_carousel_" + pozice,
      item_list_name: "blog " + pozice,
      transaction_id: order.orderNo || "",
      currency: order.currencyCode || "CZK",
      value: Math.round(hodnota * 100) / 100,
      items: polozky.map(function (p, i) {
        return { item_id: String(p.id || ""), item_name: p.name,
                 price: p.price, quantity: p.quantity, index: i,
                 item_list_id: "blog_carousel_" + pozice };
      }),
    };
    if (typeof window.gtag === "function") window.gtag("event", "blog_carousel_purchase", params);
    else {
      window.dataLayer = window.dataLayer || [];
      window.dataLayer.push({ ecommerce: null });
      window.dataLayer.push({ event: "blog_carousel_purchase", ecommerce: params });
    }
  }

  function spust() {
    var order = objednavka();
    if (!order || !order.content || !order.content.length) return;

    var kliky = [];
    try { kliky = JSON.parse(sessionStorage.getItem("ppcar_clicks") || "[]"); } catch (e) { return; }
    if (!kliky.length) return;

    var hranice = Date.now() - OKNO_HODIN * 3600 * 1000;
    kliky = kliky.filter(function (k) { return !k.ts || k.ts >= hranice; });
    if (!kliky.length) return;

    /* pro kazdou pozici (top/bottom) posbirej koupene polozky, na ktere
       clovek predtim v te pozici kliknul */
    var podlePozice = {};
    order.content.forEach(function (item) {
      var id = String(item.id || "");
      var jmeno = norm(item.name);
      for (var i = 0; i < kliky.length; i++) {
        var k = kliky[i];
        var sedi = (k.pid && id && k.pid === id) || (jmeno && norm(k.name) === jmeno);
        if (!sedi) continue;
        var poz = k.pozice || "top";
        (podlePozice[poz] = podlePozice[poz] || []).push({
          id: id, name: item.name,
          price: parseFloat(item.price) || 0,
          quantity: parseInt(item.quantity, 10) || 1,
        });
        break;   // jednu koupenou polozku zapocitej jen jednou
      }
    });

    Object.keys(podlePozice).forEach(function (poz) {
      posli(poz, podlePozice[poz], order);
    });

    try { sessionStorage.removeItem("ppcar_clicks"); } catch (e) { /* nic */ }
  }

  try {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", function () { setTimeout(spust, 1200); });
    } else {
      setTimeout(spust, 1200);   // dat Shoptetu cas naplnit dataLayer
    }
  } catch (e) { /* mereni nesmi rozbit dekovaci stranku */ }
})();
