// Header behaviour (no inline scripts: the CSP forbids them) and the live updates of every page.
(function () {
  "use strict";
  // language: a plain select; the server remembers the choice in a cookie
  document.querySelectorAll("[data-lang-select]").forEach(function (sel) {
    sel.addEventListener("change", function () {
      var u = new URL(location.href); u.searchParams.set("lang", sel.value); location.href = u.toString();
    });
  });
  // account menu: closes on outside click and Escape
  var menu = document.querySelector("details.usermenu");
  if (menu) {
    document.addEventListener("click", function (e) { if (menu.open && !menu.contains(e.target)) { menu.open = false; } });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && menu.open) { menu.open = false; menu.querySelector("summary").focus(); } });
  }
  // every "..." menu next to a card closes the same way
  document.addEventListener("click", function (e) {
    document.querySelectorAll("details.more[open]").forEach(function (d) { if (!d.contains(e.target)) { d.open = false; } });
  });

  // Live updates: a region marked data-live="id" is refreshed from the server every few seconds (data-live-every="10" = slower).
  // The page is fetched again and only the marked regions are swapped; a region that holds the focus is left alone.
  // data-live-keys on a container lists what the page shows (e.g. the devices): when that list changes the page reloads.
  var regions = document.querySelectorAll("[data-live]");
  if (!regions.length && !document.querySelector("[data-live-keys]")) { return; }
  var every = 5;
  regions.forEach(function (r) { var n = parseInt(r.getAttribute("data-live-every") || "5", 10); if (n > every) { every = n; } });
  var busy = false;
  function tick() {
    if (document.hidden || busy) { return; }
    busy = true;
    fetch(location.pathname + location.search, { credentials: "same-origin", headers: { "X-Live": "1" } }).then(function (r) {
      if (r.redirected && /\/login/.test(r.url)) { location.href = r.url; return null; }
      return r.ok ? r.text() : null;
    }).then(function (text) {
      if (!text) { return; }
      var doc = new DOMParser().parseFromString(text, "text/html");
      doc.querySelectorAll("[data-live]").forEach(function (fresh) {
        var cur = document.querySelector('[data-live="' + fresh.getAttribute("data-live") + '"]');
        if (cur && cur.innerHTML !== fresh.innerHTML && !cur.contains(document.activeElement)) { cur.innerHTML = fresh.innerHTML; }
      });
      var k = document.querySelector("[data-live-keys]"), nk = doc.querySelector("[data-live-keys]");
      if (k && nk && k.getAttribute("data-live-keys") !== nk.getAttribute("data-live-keys") && !document.querySelector("dialog[open]")) { location.reload(); }
    }).catch(function () {}).then(function () { busy = false; });
  }
  setInterval(tick, every * 1000);
  document.addEventListener("visibilitychange", function () { if (!document.hidden) { tick(); } });
  window.dbaLiveTick = tick;                                                  // for tests
})();
