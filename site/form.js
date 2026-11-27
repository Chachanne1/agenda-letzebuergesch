// Formulaire pour proposer une activité. Envoie du JSON au relais Cloudflare ; ne publie rien directement.
(function () {
  "use strict";
  const cfg = window.AGENDA_FORM || {};
  const btn = document.getElementById("proposeBtn");
  const dlg = document.getElementById("proposeDlg");
  if (!btn || !dlg || !cfg.endpoint || !cfg.turnstileSiteKey || typeof dlg.showModal !== "function") return;
  btn.hidden = false;

  const form = document.getElementById("proposeForm");
  const msg = document.getElementById("proposeMsg");
  const submit = document.getElementById("proposeSend");
  const slot = document.getElementById("proposeCaptcha");
  let widgetId = null, token = "", scriptState = "idle";

  const ERR = {
    required: "Dëst Feld ass obligatoresch.",
    length: "Den Text ass ze kuerz oder ze laang.",
    format: "D'Format ass net valabel.",
    past: "D'Datum ass scho laang eriwwer.",
    range: "D'Datum ass ze wäit ewech oder huet keng gëlteg Reiefolleg.",
    scheme: "De Link muss mat https:// ufänken.",
    host: "Dëse Link gesäit net valabel aus.",
    shortener: "Kuerz Linken (z. B. bit.ly) sinn net erlaabt. Gëff w.e.g. de ganze Link un.",
    chars: "Zeechen wéi < an > sinn net erlaabt.",
    links: "Hei sinn keng Linken erlaabt (de Link kënnt an dat eegent Feld).",
    unconfirmed: "Bestätegt w.e.g., datt d'Aktivitéit op Lëtzebuergesch ass.",
  };
  const FIELD_IDS = { title: "p_title", date: "p_date", end_date: "p_end", time: "p_time", venue: "p_venue", address: "p_address", description: "p_desc", url: "p_url", lb_confirm: "p_lb" };

  function loadTurnstile() {
    if (scriptState === "ready") return Promise.resolve();
    return new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
      s.async = true;
      s.onload = () => { scriptState = "ready"; resolve(); };
      s.onerror = () => reject(new Error("captcha-script"));
      document.head.appendChild(s);
    });
  }
  function renderCaptcha() {
    token = ""; submit.disabled = true;
    if (widgetId !== null && window.turnstile) { window.turnstile.reset(widgetId); return; }
    widgetId = window.turnstile.render(slot, {
      sitekey: cfg.turnstileSiteKey,
      callback: (t) => { token = t; submit.disabled = false; },
      "expired-callback": () => { token = ""; submit.disabled = true; },
      "error-callback": () => { token = ""; submit.disabled = true; },
    });
  }
  function say(text, kind) { msg.textContent = text; msg.dataset.kind = kind || ""; }
  function clearErrors() { form.querySelectorAll("[aria-invalid]").forEach((el) => { el.removeAttribute("aria-invalid"); }); form.querySelectorAll(".ferr").forEach((el) => el.remove()); }
  function showErrors(errors) {
    let first = null;
    Object.entries(errors || {}).forEach(([field, code]) => {
      const el = document.getElementById(FIELD_IDS[field] || "");
      if (!el) return;
      el.setAttribute("aria-invalid", "true");
      const p = document.createElement("p"); p.className = "ferr"; p.textContent = ERR[code] || ERR.format;
      el.closest(".f").appendChild(p);
      first = first || el;
    });
    if (first) first.focus();
  }

  btn.addEventListener("click", () => {
    form.hidden = false; document.getElementById("proposeDone").hidden = true; say("");
    dlg.showModal();
    loadTurnstile().then(renderCaptcha).catch(() => say("De Schutz géint Spam konnt net gelueden ginn. Probéier et méi spéit nach eng Kéier.", "err"));
  });
  document.getElementById("proposeCancel").addEventListener("click", () => dlg.close());
  document.getElementById("proposeClose").addEventListener("click", () => dlg.close());
  dlg.addEventListener("click", (ev) => { if (ev.target === dlg) dlg.close(); });
  const min = new Date(); document.getElementById("p_date").min = min.toISOString().slice(0, 10);

  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    clearErrors(); say("");
    if (!token) { say("Waart w.e.g., bis de Spam-Schutz fäerdeg ass.", "err"); return; }
    const v = (id) => document.getElementById(id).value;
    const body = {
      title: v("p_title"), date: v("p_date"), end_date: v("p_end"), time: v("p_time"),
      venue: v("p_venue"), address: v("p_address"), description: v("p_desc"), url: v("p_url"),
      lb_confirm: document.getElementById("p_lb").checked,
      website: v("p_website"), token,
    };
    submit.disabled = true; say("Ech schécken et…");
    try {
      const r = await fetch(cfg.endpoint, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const data = await r.json().catch(() => ({}));
      if (r.ok && data.ok) {
        form.reset(); form.hidden = true; say("");
        document.getElementById("proposeDone").hidden = false;
        document.getElementById("proposeDoneClose").focus();
        return;
      }
      if (data.error === "invalid") { say("Kuck w.e.g. d'Felder no, déi markéiert sinn.", "err"); showErrors(data.errors); }
      else if (data.error === "captcha") say("De Spam-Schutz huet d'Ufro net akzeptéiert. Probéier et nach eng Kéier.", "err");
      else say("Et ass e Feeler geschitt. Probéier et méi spéit nach eng Kéier.", "err");
    } catch (_) {
      say("Keng Verbindung. Probéier et méi spéit nach eng Kéier.", "err");
    }
    renderCaptcha(); // un token n'est utilisable qu'une fois
  });
  document.getElementById("proposeDoneClose").addEventListener("click", () => dlg.close());
})();
