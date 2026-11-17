// Charge data/events.json, groupe par jour et filtre. Aucune dépendance.
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const DAYS = ["Sonndeg", "Méindeg", "Dënschdeg", "Mëttwoch", "Donneschdeg", "Freideg", "Samschdeg"];
  const MONTHS = ["Januar", "Februar", "Mäerz", "Abrëll", "Mee", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"];
  const PAGE_DAYS = 30;

  let events = [];
  let range = "all";
  let shownDays = PAGE_DAYS;

  const iso = (d) => d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
  const parse = (s) => new Date(s + "T00:00");
  const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
  const esc = (s) => String(s || "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const safeUrl = (u) => (/^https?:\/\//i.test(u || "") ? u : "");
  const longDate = (s) => { const d = parse(s); return d.getDate() + ". " + MONTHS[d.getMonth()]; };
  const timeOf = (e) => {
    const m = /T(\d{2}:\d{2})/.exec(e.start || "");
    return m && m[1] !== "00:00" ? m[1].replace(":", "h") : "";
  };

  // bornes des raccourcis de période
  function bounds(r) {
    const today = new Date();
    const t = iso(today);
    if (r === "today") return [t, t];
    if (r === "week") return [t, iso(addDays(today, (7 - today.getDay()) % 7))];
    if (r === "weekend") {
      const dow = today.getDay();
      const sat = dow === 0 ? addDays(today, -1) : addDays(today, 6 - dow);
      return [iso(dow === 0 || dow === 6 ? today : sat), iso(addDays(sat, 1))];
    }
    if (r === "month") return [t, iso(new Date(today.getFullYear(), today.getMonth() + 1, 0))];
    return ["", ""];
  }

  function currentFilter() {
    let [from, to] = range === "custom" ? [$("from").value, $("to").value] : bounds(range);
    return { q: $("q").value.trim().toLowerCase(), venue: $("venue").value, from, to, onlyOk: $("onlyok").checked };
  }

  function visible(f) {
    const today = iso(new Date());
    return events.filter((e) => {
      const s = e.start.slice(0, 10);
      const end = (e.end || e.start).slice(0, 10);
      if (end < today) return false;
      if (f.onlyOk && e.status === "probable") return false;
      if (f.venue && e.venue !== f.venue) return false;
      if (f.from && end < f.from) return false;
      if (f.to && s > f.to) return false;
      if (f.q && !(e.title + " " + e.venue + " " + e.description).toLowerCase().includes(f.q)) return false;
      return true;
    });
  }

  function eventHtml(e) {
    const url = safeUrl(e.url);
    const title = url ? `<a href="${esc(url)}" target="_blank" rel="noopener">${esc(e.title)}</a>` : esc(e.title);
    const s = e.start.slice(0, 10), end = (e.end || "").slice(0, 10);
    const time = timeOf(e);
    const when = [time, end && end !== s ? "bis den " + longDate(end) : ""].filter(Boolean).join(" · ") || "ganzdaags";
    const desc = String(e.description || "").trim();
    const long = desc.length > 150;
    return `<li class="ev${e.status === "probable" ? " ev--maybe" : ""}">
      <div class="ev__when">${esc(when)}</div>
      <h3 class="ev__title">${title}</h3>
      <p class="ev__where">${esc(e.venue)}${e.address ? ", " + esc(e.address) : ""}</p>
      ${e.status === "probable" ? '<span class="maybe">Sprooch nach net bestätegt</span>' : ""}
      ${desc ? `<p class="ev__desc${long ? " is-clamped" : ""}">${esc(desc)}</p>` : ""}
      ${long ? '<button type="button" class="ev__toggle" aria-expanded="false">Méi liesen</button>' : ""}
      <p class="ev__src">Quell: ${esc(e.source)}</p>
    </li>`;
  }

  function render() {
    const f = currentFilter();
    const list = visible(f);
    const today = iso(new Date());

    // un événement qui court déjà apparaît à la date du jour
    const groups = new Map();
    list.forEach((e) => {
      const day = e.start.slice(0, 10) < today ? today : e.start.slice(0, 10);
      if (!groups.has(day)) groups.set(day, []);
      groups.get(day).push(e);
    });
    const keys = [...groups.keys()].sort();

    $("count").textContent = list.length + (list.length === 1 ? " Aktivitéit" : " Aktivitéiten");
    $("empty").hidden = list.length > 0;
    $("more").hidden = keys.length <= shownDays;
    $("list").innerHTML = keys.slice(0, shownDays).map((k) => {
      const d = parse(k);
      return `<section class="day" aria-label="${esc(DAYS[d.getDay()] + " " + longDate(k))}">
        <div class="day__rail"><span class="day__n">${d.getDate()}</span>
          <span><span class="day__w">${DAYS[d.getDay()]}</span><span class="day__m">${MONTHS[d.getMonth()]} ${d.getFullYear()}</span></span></div>
        <ul class="day__list">${groups.get(k).map(eventHtml).join("")}</ul>
      </section>`;
    }).join("");
    saveState();
  }

  // l'état des filtres est gardé dans l'adresse pour pouvoir la partager
  function saveState() {
    const p = new URLSearchParams();
    if ($("q").value.trim()) p.set("q", $("q").value.trim());
    if ($("venue").value) p.set("plaz", $("venue").value);
    if (range !== "all") p.set("zait", range);
    if (range === "custom") { if ($("from").value) p.set("vun", $("from").value); if ($("to").value) p.set("bis", $("to").value); }
    if ($("onlyok").checked) p.set("bestaeteg", "1");
    const qs = p.toString();
    history.replaceState(null, "", qs ? "?" + qs : location.pathname);
  }

  function loadState() {
    const p = new URLSearchParams(location.search);
    $("q").value = p.get("q") || "";
    if (p.get("plaz")) $("venue").value = p.get("plaz");
    $("onlyok").checked = p.get("bestaeteg") === "1";
    const z = p.get("zait");
    range = ["today", "week", "weekend", "month", "custom"].includes(z) ? z : "all";
    if (range === "custom") { $("from").value = p.get("vun") || ""; $("to").value = p.get("bis") || ""; $("from").closest("details").open = true; }
    syncChips();
  }

  function syncChips() {
    document.querySelectorAll(".chip").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.range === range)));
  }

  function fillVenues() {
    const venues = [...new Set(events.map((e) => e.venue).filter(Boolean))].sort((a, b) => a.localeCompare(b));
    $("venue").insertAdjacentHTML("beforeend", venues.map((v) => `<option value="${esc(v)}">${esc(v)}</option>`).join(""));
  }

  function reset() {
    $("q").value = ""; $("venue").value = ""; $("from").value = ""; $("to").value = ""; $("onlyok").checked = false;
    range = "all"; shownDays = PAGE_DAYS; syncChips(); render();
  }

  document.querySelectorAll(".chip").forEach((b) => b.addEventListener("click", () => {
    range = b.dataset.range; $("from").value = ""; $("to").value = ""; shownDays = PAGE_DAYS; syncChips(); render();
  }));
  ["from", "to"].forEach((id) => $(id).addEventListener("input", () => { range = "custom"; shownDays = PAGE_DAYS; syncChips(); render(); }));
  ["q", "venue", "onlyok"].forEach((id) => $(id).addEventListener("input", () => { shownDays = PAGE_DAYS; render(); }));
  $("reset").addEventListener("click", reset);
  $("more").addEventListener("click", () => { shownDays += PAGE_DAYS; render(); });
  $("list").addEventListener("click", (ev) => {
    const b = ev.target.closest(".ev__toggle");
    if (!b) return;
    const p = b.previousElementSibling;
    const open = p.classList.toggle("is-clamped") === false;
    b.textContent = open ? "Manner liesen" : "Méi liesen";
    b.setAttribute("aria-expanded", String(open));
  });

  fetch("data/events.json")
    .then((r) => r.json())
    .then((data) => {
      events = data.sort((a, b) => a.start.localeCompare(b.start));
      fillVenues(); loadState(); render();
    })
    .catch(() => { $("count").textContent = "D'Daten konnten net gelueden ginn. Lued d'Säit nei."; });

  // date de la dernière mise à jour (écrite par build.py)
  fetch("data/meta.json").then((r) => r.json()).then((m) => {
    if (m.updated) { const d = new Date(m.updated); $("updated").textContent = "Lescht Aktualiséierung: " + d.getDate() + ". " + MONTHS[d.getMonth()] + " " + d.getFullYear(); }
  }).catch(() => {});
})();
