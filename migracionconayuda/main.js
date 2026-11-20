(function () {
  "use strict";
  var doc = document.documentElement;
  doc.classList.add("js");
  function safe(fn) { try { fn(); } catch (e) { if (window.console) console.warn(e); } }

  function initReveal() {
    var els = Array.prototype.slice.call(document.querySelectorAll(".reveal"));
    function showAll() { els.forEach(function (el) { el.classList.add("in"); }); }
    if (!("IntersectionObserver" in window)) { showAll(); return; }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); }
      });
    }, { threshold: 0.05, rootMargin: "0px 0px -40px 0px" });
    els.forEach(function (el) { io.observe(el); });
    setTimeout(showAll, 3500); // safety net
  }

  function initHeader() {
    var h = document.querySelector("[data-header]");
    if (!h) return;
    function on() { h.classList.toggle("scrolled", window.scrollY > 10); }
    on(); window.addEventListener("scroll", on, { passive: true });
  }

  function initMenu() {
    var btn = document.querySelector("[data-menu]");
    if (!btn) return;
    btn.addEventListener("click", function () {
      var open = document.body.classList.toggle("menu-open");
      btn.setAttribute("aria-expanded", open ? "true" : "false");
    });
    Array.prototype.forEach.call(document.querySelectorAll("[data-nav] a"), function (a) {
      a.addEventListener("click", function () {
        document.body.classList.remove("menu-open");
        btn.setAttribute("aria-expanded", "false");
      });
    });
  }

  function initNavState() {
    var here = location.pathname.split("/").pop() || "index.html";
    Array.prototype.forEach.call(document.querySelectorAll(".main-nav a, .tabbar a"), function (a) {
      var h = a.getAttribute("href") || "";
      if (/^https?:/.test(h) || h.indexOf("#") > -1 || h.indexOf("en/") === 0 || h.indexOf("../") === 0) return;
      if (h === here) a.setAttribute("aria-current", "page");
    });
  }

  function initMenuClose() {
    var btn = document.querySelector("[data-menu]");
    if (!btn) return;
    function close() { document.body.classList.remove("menu-open"); btn.setAttribute("aria-expanded", "false"); }
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && document.body.classList.contains("menu-open")) { close(); btn.focus(); } });
    document.addEventListener("click", function (e) {
      if (document.body.classList.contains("menu-open") && !e.target.closest("[data-nav]") && !e.target.closest("[data-menu]")) close();
    });
    window.addEventListener("resize", function () { if (window.innerWidth > 1060) close(); });
  }

  function initYear() {
    var y = document.querySelector("[data-year]");
    if (y) y.textContent = new Date().getFullYear();
  }

  function initForm() {
    var form = document.querySelector("[data-form]");
    if (!form || !window.fetch || !window.FormData) return;
    var status = form.querySelector("[data-status]");
    var btn = form.querySelector("button[type=submit]");
    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var label = btn.innerHTML;
      btn.disabled = true;
      btn.textContent = form.getAttribute("data-sending");
      status.className = "form-status"; status.textContent = "";
      fetch(form.action, { method: "POST", body: new FormData(form), headers: { "Accept": "application/json" } })
        .then(function (r) { return r.json().catch(function () { return { ok: false }; }); })
        .then(function (d) {
          if (d && d.ok) {
            status.className = "form-status ok"; status.textContent = form.getAttribute("data-ok"); form.reset();
          } else { throw new Error("fail"); }
        })
        .catch(function () { status.className = "form-status err"; status.textContent = form.getAttribute("data-err"); })
        .then(function () { btn.disabled = false; btn.innerHTML = label; });
    });
  }

  function boot() { safe(initReveal); safe(initHeader); safe(initMenu); safe(initMenuClose); safe(initNavState); safe(initYear); safe(initForm); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();
})();
