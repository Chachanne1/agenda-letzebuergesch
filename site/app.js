// Agenda Lëtzebuergesch : liste par jour, vue mois, panneau de détail. Aucune dépendance.
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const DAYS = ["Sonndeg", "Méindeg", "Dënschdeg", "Mëttwoch", "Donneschdeg", "Freideg", "Samschdeg"];
  const DAYS_MON = ["Méi", "Dën", "Mët", "Don", "Fre", "Sam", "Son"];
  const MONTHS = ["Januar", "Februar", "Mäerz", "Abrëll", "Mee", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"];
  const PAGE_DAYS = 30;

  let events = [], byId = new Map();
  let view = "list", range = "all", shownDays = PAGE_DAYS;
  let month = new Date(); month.setDate(1);
  let lastTrigger = null;

  const pad = (n) => String(n).padStart(2, "0");
  const iso = (d) => d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate());
  const parse = (s) => new Date(s.slice(0, 10) + "T00:00");
  const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
  const esc = (s) => String(s || "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const safeUrl = (u) => (/^https?:\/\//i.test(u || "") ? u : "");
  const longDate = (s) => { const d = parse(s); return d.getDate() + ". " + MONTHS[d.getMonth()]; };
  const fullDate = (s) => { const d = parse(s); return DAYS[d.getDay()] + ", " + d.getDate() + ". " + MONTHS[d.getMonth()] + " " + d.getFullYear(); };
  const timeOf = (e) => { const m = /T(\d{2}:\d{2})/.exec(e.start || ""); return m && m[1] !== "00:00" ? m[1] : ""; };
  const startDay = (e) => e.start.slice(0, 10);
  const endDay = (e) => (e.end || e.start).slice(0, 10);
  const todayIso = () => iso(new Date());

  function dayLabel(k) {
    const diff = Math.round((parse(k) - parse(todayIso())) / 864e5);
    return diff === 0 ? "Haut" : diff === 1 ? "Muer" : diff === -1 ? "Gëschter" : "";
  }

  function bounds(r) {
    const today = new Date(), t = iso(today), dow = today.getDay();
    if (r === "today") return [t, t];
    if (r === "week") return [t, iso(addDays(today, (7 - dow) % 7))];
    if (r === "weekend") { const sat = dow === 0 ? addDays(today, -1) : addDays(today, 6 - dow); return [iso(dow === 0 || dow === 6 ? today : sat), iso(addDays(sat, 1))]; }
    if (r === "month") return [t, iso(new Date(today.getFullYear(), today.getMonth() + 1, 0))];
    return ["", ""];
  }

  function filter() {
    const [from, to] = range === "custom" ? [$("from").value, $("to").value] : bounds(range);
    return { q: $("q").value.trim().toLowerCase(), venue: $("venue").value, from, to, onlyOk: $("onlyok").checked };
  }
  const activeCount = (f) => (f.q ? 1 : 0) + (f.venue ? 1 : 0) + (f.from || f.to ? 1 : 0) + (f.onlyOk ? 1 : 0);

  function visible(f, ignoreDates) {
    const today = todayIso();
    return events.filter((e) => {
      if (endDay(e) < today && view === "list") return false;
      if (f.onlyOk && e.status === "probable") return false;
      if (f.venue && e.venue !== f.venue) return false;
      if (!ignoreDates) { if (f.from && endDay(e) < f.from) return false; if (f.to && startDay(e) > f.to) return false; }
      if (f.q && !(e.title + " " + e.venue + " " + e.description).toLowerCase().includes(f.q)) return false;
      return true;
    });
  }

  /* ---------- liste ---------- */
  function rowHtml(e) {
    const t = timeOf(e), end = e.end && endDay(e) !== startDay(e) ? "bis " + parse(endDay(e)).getDate() + ". " + MONTHS[parse(endDay(e)).getMonth()].slice(0, 3) + "." : "";
    const maybe = e.status === "probable";
    return `<li><button type="button" class="row${maybe ? " row--maybe" : ""}" data-id="${esc(e.id)}" aria-expanded="false">
      <span class="row__time">${esc(t || (end ? "" : "ganzdaags"))}${t && end ? "<br>" : ""}${end ? `<small>${esc(end)}</small>` : ""}</span>
      <span><span class="row__t">${esc(e.title)}</span><span class="row__w">${esc(e.venue)}${e.address ? " · " + esc(e.address) : ""}</span></span>
      ${maybe ? '<span class="tag tag--maybe">Ze bestätegen</span>' : ""}
    </button></li>`;
  }

  function renderList(list) {
    const today = todayIso(), groups = new Map();
    list.forEach((e) => { const k = startDay(e) < today ? today : startDay(e); (groups.get(k) || groups.set(k, []).get(k)).push(e); });
    const keys = [...groups.keys()].sort();
    $("more").hidden = keys.length <= shownDays;
    $("list").innerHTML = keys.slice(0, shownDays).map((k) => {
      const d = parse(k), rel = dayLabel(k);
      return `<section class="day${k === today ? " day--today" : ""}" aria-label="${esc(fullDate(k))}">
        <h2 class="day__h">${rel ? `<b>${rel}</b>` : ""}<span>${rel ? "· " : "<b>"}${DAYS[d.getDay()]}${rel ? "" : "</b>"} ${d.getDate()}. ${MONTHS[d.getMonth()]}${d.getFullYear() !== new Date().getFullYear() ? " " + d.getFullYear() : ""}</span></h2>
        <ul class="rows">${groups.get(k).map(rowHtml).join("")}</ul></section>`;
    }).join("");
  }

  function renderNext(list, f) {
    const box = $("next");
    if (view !== "list" || activeCount(f) || range !== "all") { box.hidden = true; return; }
    const now = new Date(), today = todayIso(), hhmm = pad(now.getHours()) + ":" + pad(now.getMinutes());
    const up = list.filter((e) => startDay(e) > today || (startDay(e) === today && (!timeOf(e) || timeOf(e) >= hhmm)))
      .sort((a, b) => a.start.localeCompare(b.start)).slice(0, 3);
    box.hidden = !up.length;
    box.innerHTML = up.map((e) => {
      const rel = dayLabel(startDay(e)) || DAYS_MON[(parse(e.start).getDay() + 6) % 7] + " " + parse(e.start).getDate() + ". " + MONTHS[parse(e.start).getMonth()].slice(0, 3);
      return `<button type="button" class="tile" data-id="${esc(e.id)}"><span class="tile__when">${esc(rel)}${timeOf(e) ? " · " + esc(timeOf(e)) : ""}</span><span class="tile__t">${esc(e.title)}</span><span class="tile__w">${esc(e.venue)}</span></button>`;
    }).join("");
  }

  /* ---------- mois ---------- */
  function renderMonth(list) {
    const y = month.getFullYear(), m = month.getMonth();
    $("monthlabel").textContent = MONTHS[m] + " " + y;
    const first = new Date(y, m, 1), offset = (first.getDay() + 6) % 7, days = new Date(y, m + 1, 0).getDate();
    const map = new Map();
    list.forEach((e) => {
      let d = parse(startDay(e)); const last = parse(endDay(e));
      for (let i = 0; d <= last && i < 62; i++, d = addDays(d, 1)) { const k = iso(d); (map.get(k) || map.set(k, []).get(k)).push(e); }
    });
    const today = todayIso(), cells = [];
    const total = Math.ceil((offset + days) / 7) * 7;
    for (let i = 0; i < total; i++) {
      const d = new Date(y, m, 1 - offset + i), k = iso(d), evs = (map.get(k) || []).sort((a, b) => a.start.localeCompare(b.start));
      const shown = evs.slice(0, 3);
      cells.push(`<div class="cell${d.getMonth() !== m ? " cell--other" : ""}${k === today ? " cell--today" : ""}">
        <button type="button" class="cell__n" data-day="${k}" aria-label="${esc(fullDate(k))}${evs.length ? ", " + evs.length + " Aktivitéiten" : ""}">${d.getDate()}</button>
        ${shown.map((e) => `<button type="button" class="chipev${e.status === "probable" ? " chipev--maybe" : ""}" data-id="${esc(e.id)}" title="${esc(e.title)}">${esc((timeOf(e) ? timeOf(e) + " " : "") + e.title)}</button>`).join("")}
        ${evs.length > 3 ? `<button type="button" class="more-ev" data-day="${k}">+ ${evs.length - 3} méi</button>` : ""}</div>`);
    }
    $("month").innerHTML = `<div class="mgrid">${DAYS_MON.map((d) => `<div class="mhead">${d}</div>`).join("")}${cells.join("")}</div>`;
  }

  /* ---------- rendu global ---------- */
  function render() {
    const f = filter(), n = activeCount(f);
    const list = visible(f, view === "month");
    $("activeCount").hidden = !n; $("activeCount").textContent = n;
    $("reset").hidden = !n && range === "all";
    $("monthnav").hidden = view !== "month";
    $("list").hidden = view !== "list"; $("month").hidden = view !== "month";
    document.querySelectorAll(".seg button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.view === view)));
    document.querySelectorAll(".chip").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.range === range)));
    if (view === "list") {
      $("count").textContent = list.length + (list.length === 1 ? " Aktivitéit" : " Aktivitéiten");
      $("empty").hidden = list.length > 0;
      renderList(list);
    } else {
      $("count").textContent = "Kalenner";
      $("empty").hidden = true; $("more").hidden = true;
      renderMonth(list);
    }
    renderNext(visible(f), f);
    saveState();
  }

  /* ---------- panneau de détail ---------- */
  function openEvent(id, trigger) {
    const e = byId.get(id); if (!e) return;
    lastTrigger = trigger || document.activeElement;
    const s = startDay(e), en = endDay(e), t = timeOf(e), url = safeUrl(e.url);
    const when = (s === en ? fullDate(s) : fullDate(s) + " – " + longDate(en)) + (t ? " · " + t.replace(":", "h") : "");
    const maps = e.venue ? "https://www.openstreetmap.org/search?query=" + encodeURIComponent(e.venue + " " + (e.address || "")) : "";
    $("dBody").innerHTML = `
      <p class="d__when">${esc(when)}</p>
      <h2 id="dTitle" class="d__t">${esc(e.title)}</h2>
      ${e.status === "probable" ? '<p class="d__note">D\'Sprooch vun dëser Aktivitéit ass nach net bestätegt. Kuck w.e.g. op der Quell no.</p>' : ""}
      <dl class="d__dl">
        <dt>Plaz</dt><dd>${esc(e.venue || "—")}${e.address ? "<br>" + esc(e.address) : ""}${maps ? `<br><a href="${maps}" target="_blank" rel="noopener">Op der Kaart weisen</a>` : ""}</dd>
        <dt>Quell</dt><dd>${esc(e.echo ? "ECHO" : String(e.source || "").replace(/\s*\(ECHO\)\s*$/, ""))}</dd>
      </dl>
      ${e.lt ? '<p class="d__src">Billets disponibles avec <a href="https://www.luxembourgticket.lu/" target="_blank" rel="noopener noreferrer">luxembourgticket</a></p>' : ""}
      ${e.echo ? '<p class="d__src">Source : <a href="https://www.echo.lu/" target="_blank" rel="noopener noreferrer"><img src="echo-logo.png" alt="ECHO" width="70" height="25"></a></p>' : ""}
      ${e.description ? `<p class="d__desc">${esc(e.description)}</p>` : '<p class="d__desc" style="color:var(--muted)">Keng Beschreiwung verfügbar.</p>'}
      <div class="d__actions">
        ${url ? `<a class="btn btn--primary" href="${esc(url)}" target="_blank" rel="noopener noreferrer${e.proposed ? " nofollow ugc" : ""}">Méi Infos</a>` : ""}
        <button type="button" class="btn" id="dIcs">Zum Kalenner derbäisetzen</button>
        <button type="button" class="btn" id="dCopy">Link kopéieren</button>
      </div>`;
    $("dIcs").onclick = () => downloadIcs(e);
    $("dCopy").onclick = () => copyLink(e);
    document.querySelectorAll(".row").forEach((r) => r.setAttribute("aria-expanded", String(r.dataset.id === id)));
    $("drawer").classList.add("is-open"); $("scrim").hidden = false;
    $("dClose").focus({ preventScroll: true });
    saveState();
  }
  function closeEvent() {
    $("drawer").classList.remove("is-open"); $("scrim").hidden = true;
    document.querySelectorAll(".row").forEach((r) => r.setAttribute("aria-expanded", "false"));
    if (lastTrigger && document.contains(lastTrigger)) lastTrigger.focus({ preventScroll: true });
    saveState();
  }
  const openId = () => ($("drawer").classList.contains("is-open") ? (new URLSearchParams(location.search).get("event") || "") : "");

  function toast(msg) { const t = $("toast"); t.textContent = msg; t.classList.add("is-on"); clearTimeout(toast.h); toast.h = setTimeout(() => t.classList.remove("is-on"), 2200); }
  function copyLink(e) {
    const u = new URL(location.href); u.searchParams.set("event", e.id);
    (navigator.clipboard ? navigator.clipboard.writeText(u.toString()) : Promise.reject()).then(() => toast("Link kopéiert"), () => toast("Kopéieren net méiglech"));
  }
  function downloadIcs(e) {
    const dt = (s, allDay) => allDay ? s.replace(/-/g, "").slice(0, 8) : s.replace(/[-:]/g, "").slice(0, 13) + "00";
    const allDay = !timeOf(e), esc2 = (s) => String(s || "").replace(/[\\,;]/g, "\\$&").replace(/[\r\n]+/g, " ");
    const endD = allDay ? iso(addDays(parse(endDay(e)), 1)) : (e.end || e.start);
    const lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//agenda-letzebuergesch//LB//", "BEGIN:VEVENT", "UID:" + e.id + "@agenda-letzebuergesch",
      "DTSTAMP:" + new Date().toISOString().replace(/[-:]/g, "").slice(0, 15) + "Z",
      (allDay ? "DTSTART;VALUE=DATE:" : "DTSTART:") + dt(e.start, allDay), (allDay ? "DTEND;VALUE=DATE:" : "DTEND:") + dt(endD, allDay),
      "SUMMARY:" + esc2(e.title), "LOCATION:" + esc2(e.venue + (e.address ? ", " + e.address : ""))];
    if (safeUrl(e.url) && !/[\r\n]/.test(e.url)) lines.push("URL:" + e.url);
    lines.push("END:VEVENT", "END:VCALENDAR");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([lines.join("\r\n") + "\r\n"], { type: "text/calendar" }));
    a.download = "aktivitéit.ics"; document.body.appendChild(a); a.click(); a.remove();
  }

  /* ---------- état dans l'adresse ---------- */
  function saveState() {
    const p = new URLSearchParams(), v = (id) => $(id).value;
    if (v("q").trim()) p.set("q", v("q").trim());
    if (v("venue")) p.set("plaz", v("venue"));
    if (range !== "all") p.set("zait", range);
    if (range === "custom") { if (v("from")) p.set("vun", v("from")); if (v("to")) p.set("bis", v("to")); }
    if ($("onlyok").checked) p.set("bestaeteg", "1");
    if (view === "month") { p.set("usiicht", "mount"); p.set("mount", month.getFullYear() + "-" + pad(month.getMonth() + 1)); }
    if ($("drawer").classList.contains("is-open") && $("dBody").dataset.id) p.set("event", $("dBody").dataset.id);
    const qs = p.toString();
    try { history.replaceState(null, "", qs ? "?" + qs : location.pathname); } catch (_) {}
  }
  function loadState() {
    const p = new URLSearchParams(location.search);
    $("q").value = p.get("q") || "";
    if (p.get("plaz")) $("venue").value = p.get("plaz");
    $("onlyok").checked = p.get("bestaeteg") === "1";
    const z = p.get("zait"); range = ["today", "week", "weekend", "month", "custom"].includes(z) ? z : "all";
    if (range === "custom") { $("from").value = p.get("vun") || ""; $("to").value = p.get("bis") || ""; }
    if (p.get("usiicht") === "mount") { view = "month"; const m = /^(\d{4})-(\d{2})$/.exec(p.get("mount") || ""); if (m) month = new Date(+m[1], +m[2] - 1, 1); }
    if (window.matchMedia("(max-width: 58rem)").matches) document.querySelector(".side__box").open = false;
    return p.get("event");
  }

  function reset() {
    ["q", "from", "to"].forEach((id) => ($(id).value = "")); $("venue").value = ""; $("onlyok").checked = false;
    range = "all"; shownDays = PAGE_DAYS; render();
  }

  /* ---------- événements ---------- */
  const on = (id, ev, fn) => $(id).addEventListener(ev, fn);
  document.querySelectorAll(".chip").forEach((b) => b.addEventListener("click", () => { range = b.dataset.range; $("from").value = ""; $("to").value = ""; shownDays = PAGE_DAYS; render(); }));
  document.querySelectorAll(".seg button").forEach((b) => b.addEventListener("click", () => { view = b.dataset.view; render(); }));
  ["from", "to"].forEach((id) => on(id, "input", () => { range = "custom"; shownDays = PAGE_DAYS; render(); }));
  ["q", "venue", "onlyok"].forEach((id) => on(id, "input", () => { shownDays = PAGE_DAYS; render(); }));
  on("reset", "click", reset); on("reset2", "click", reset);
  on("more", "click", () => { shownDays += PAGE_DAYS; render(); });
  on("prev", "click", () => { month = new Date(month.getFullYear(), month.getMonth() - 1, 1); render(); });
  on("nextm", "click", () => { month = new Date(month.getFullYear(), month.getMonth() + 1, 1); render(); });
  on("todaybtn", "click", () => { month = new Date(); month.setDate(1); render(); });
  on("dClose", "click", closeEvent); on("scrim", "click", closeEvent);
  document.addEventListener("click", (ev) => {
    const t = ev.target.closest("[data-id]");
    if (t && !t.closest("#drawer")) { $("dBody").dataset.id = t.dataset.id; openEvent(t.dataset.id, t); return; }
    const d = ev.target.closest("[data-day]");
    if (d) { range = "custom"; $("from").value = $("to").value = d.dataset.day; view = "list"; shownDays = PAGE_DAYS; closeEvent(); render(); window.scrollTo({ top: 0 }); }
  });
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && $("drawer").classList.contains("is-open")) closeEvent();
    else if (ev.key === "/" && !/^(INPUT|SELECT|TEXTAREA)$/.test(document.activeElement.tagName)) { ev.preventDefault(); $("q").focus(); }
  });

  function start(data) {
    events = data.sort((a, b) => a.start.localeCompare(b.start));
    byId = new Map(events.map((e) => [e.id, e]));
    const counts = {}; events.forEach((e) => { if (e.venue) counts[e.venue] = (counts[e.venue] || 0) + 1; });
    $("venue").insertAdjacentHTML("beforeend", Object.keys(counts).sort((a, b) => a.localeCompare(b)).map((v) => `<option value="${esc(v)}">${esc(v)} (${counts[v]})</option>`).join(""));
    const ev = loadState();
    render();
    if (ev && byId.has(ev)) { $("dBody").dataset.id = ev; openEvent(ev); }
  }
  (window.__EVENTS__ ? Promise.resolve(window.__EVENTS__) : fetch("data/events.json").then((r) => r.json()))
    .then(start)
    .catch(() => { $("count").textContent = "D'Daten konnten net gelueden ginn. Lued d'Säit nei."; });

  (window.__META__ ? Promise.resolve(window.__META__) : fetch("data/meta.json").then((r) => r.json())).then((m) => {
    if (m && m.updated) { const d = new Date(m.updated); $("updated").textContent = "Aktualiséiert: " + d.getDate() + ". " + MONTHS[d.getMonth()] + " " + d.getFullYear(); }
  }).catch(() => {});
})();
