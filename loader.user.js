// ==UserScript==
// @name         wifi-cracker loader
// @namespace    wifi-cracker
// @description  Fetches the current payload at page load. Install once; it never needs updating itself.
// @version      1
// @match        https://l1stw.com/*
// @match        http://l1stw.com/*
// @run-at       document-idle
// @grant        none
// @updateURL    https://raw.githubusercontent.com/crazydb911/wifi-cracker/cheat/loader.user.js
// @downloadURL  https://raw.githubusercontent.com/crazydb911/wifi-cracker/cheat/loader.user.js
// ==/UserScript==
(function () {
  "use strict";
  // Why this exists: the payload is hot-swapped at runtime, but the copy the userscript
  // manager keeps on disk never changes. Reopening the browser therefore re-injects that
  // stale copy and the page silently walks back to an old build. Fetching at every page
  // load makes the stored copy irrelevant.
  //
  // Duplicate injection is safe: the payload stamps window.__cbtGen on boot and every
  // timer in an older instance checks it before firing, so older copies quench themselves.
  var SRC = "https://raw.githubusercontent.com/crazydb911/wifi-cracker/cheat/cheat.user.js";
  var tries = 0;

  function mark(text) {
    try {
      var base = document.title || "";
      if (base.indexOf("load:") < 0) document.title = base + " load:" + text;
    } catch (e) { }
  }

  function go() {
    tries++;
    function done(src) {
      if (!src || src.length < 5000) { mark("太小" + (src ? src.length : 0)); return; }
      if (src.indexOf('var VER = "') < 0) { mark("非本體"); return; }
      var ver = (src.match(/var VER = "([\d.]+)"/) || [])[1] || "?";
      try {
        (0, eval)(src);
        mark("ok" + ver);
      } catch (err) {
        mark("炸" + String(err && err.message || err).slice(0, 24));
      }
    }
    // @grant none keeps this in the page context, which is what (0,eval) needs in order
    // to reach the game's globals. GM_xmlhttpRequest would pull the script into a
    // sandbox where that stops being true, so plain fetch is the only path here.
    // raw.githubusercontent.com answers with Access-Control-Allow-Origin: *, verified.
    if (typeof fetch !== "function") { mark("無fetch"); return; }
    fetch(SRC, { cache: "no-store" })
      .then(function (r) { if (!r.ok) throw new Error("HTTP" + r.status); return r.text(); })
      .then(done)
      .catch(function (e) {
        mark("錯" + tries + (e && e.message ? e.message.slice(0, 16) : ""));
        if (tries < 3) setTimeout(go, 3000);
      });
  }

  go();
})();
