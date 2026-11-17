// Charge data/events.json et affiche la liste avec filtres. Aucune dépendance.
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  let events = [];

  const fmtDate = (iso) => {
    if (!iso) return "";
    const d = new Date(iso.length === 10 ? iso + "T00:00" : iso);
    const opts = iso.length === 10
      ? { weekday: "long", day: "numeric", month: "long", year: "numeric" }
      : { weekday: "long", day: "numeric", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit" };
    return d.toLocaleString("lb-LU", opts).replace("Invalid Date", iso);
  };

  const esc = (s) => String(s || "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const safeUrl = (u) => (/^https?:\/\//i.test(u || "") ? u : "");

  function render() {
    const q = $("q").value.trim().toLowerCase();
    const venue = $("venue").value;
    const from = $("from").value;
    const to = $("to").value;

    const shown = events.filter((e) => {
      const day = e.start.slice(0, 10);
      if (venue && e.venue !== venue) return false;
      if (from && day < from) return false;
      if (to && day > to) return false;
      if (q && !(e.title + " " + e.venue + " " + e.description).toLowerCase().includes(q)) return false;
      return true;
    });

    $("count").textContent = shown.length + " Aktivitéit" + (shown.length === 1 ? "" : "en");
    $("empty").hidden = shown.length > 0;
    $("list").innerHTML = shown.map((e) => {
      const url = safeUrl(e.url);
      const title = url
        ? `<a href="${esc(url)}" target="_blank" rel="noopener">${esc(e.title)}</a>`
        : esc(e.title);
      return `<li class="card">
        <time>${esc(fmtDate(e.start))}</time>
        <h2>${title}</h2>
        <p class="where">${esc(e.venue)}${e.address ? " · " + esc(e.address) : ""}</p>
        <p>${esc(e.description)}</p>
        <p class="src">Quell: ${esc(e.source)}</p>
      </li>`;
    }).join("");
  }

  function fillVenues() {
    const venues = [...new Set(events.map((e) => e.venue).filter(Boolean))].sort();
    $("venue").insertAdjacentHTML("beforeend",
      venues.map((v) => `<option value="${esc(v)}">${esc(v)}</option>`).join(""));
  }

  fetch("data/events.json")
    .then((r) => r.json())
    .then((data) => {
      events = data.sort((a, b) => a.start.localeCompare(b.start));
      fillVenues();
      render();
    })
    .catch(() => { $("count").textContent = "Donnéeë konnten net gelueden ginn."; });

  ["q", "venue", "from", "to"].forEach((id) => $(id).addEventListener("input", render));
  $("reset").addEventListener("click", () => {
    ["q", "venue", "from", "to"].forEach((id) => ($(id).value = ""));
    render();
  });
})();
