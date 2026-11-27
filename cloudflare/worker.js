/**
 * Relais du formulaire « Aktivitéit virschloen » (Cloudflare Worker, offre gratuite).
 *
 *   navigateur ──POST JSON──► ce Worker ──► issue GitHub (étiquette « proposition »)
 *
 * Le Worker ne publie RIEN : il crée seulement une issue que tu valides à la main.
 * Secrets (jamais dans le code) : GITHUB_TOKEN, TURNSTILE_SECRET.
 * Variables (wrangler / tableau de bord) : GITHUB_REPO, ALLOWED_ORIGIN.
 *
 * La validation ci-dessous est la copie JavaScript de scrapers/propositions.py
 * (mêmes cas de test : tests/validation_cases.json).
 */

const SHORTENERS = new Set([
  "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd", "buff.ly", "cutt.ly", "rebrand.ly",
  "shorturl.at", "tiny.cc", "rb.gy", "lnkd.in", "t.ly", "s.id", "v.gd", "bl.ink", "shorte.st",
  "adf.ly", "tr.ee", "qr.ae", "urlz.fr", "lc.cx", "clck.ru", "x.co", "ift.tt", "dlvr.it",
]);
const TRACKING = /^(utm_.*|fbclid|gclid|dclid|msclkid|igshid|mc_cid|mc_eid|_hsenc|_hsmi|mkt_tok|yclid)$/i;
const CONTROLS = /[\u0000-\u001f\u007f-\u009f\u00ad\u200b-\u200f\u202a-\u202e\u2060-\u2064\u2066-\u2069\ufeff]/g;
const URL_RE = /^https:\/\/([a-z0-9.-]+)(?::443)?((?:[/?#][\x21-\x7e]*)?)$/i;
const PATH_BAD = /[<>"'`\\]/;
const LABEL_RE = /^[a-z0-9]([a-z0-9-]*[a-z0-9])?$/;
const TIME_RE = /^([01]\d|2[0-3]):[0-5]\d$/;
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
const MAX_BODY = 8192;

export function normText(value) {
  if (typeof value !== "string") return "";
  return value.normalize("NFC")
    .replace(/[\t\n\r\u00a0\u2028\u2029]/g, " ")
    .replace(CONTROLS, "")
    .replace(/ {2,}/g, " ")
    .trim();
}

const len = (s) => [...s].length; // points de code, comme len() en Python

export function checkUrl(raw) {
  const s = normText(raw);
  if (!s) return ["", ""];
  if (len(s) > 300) return ["", "length"];
  if (!s.toLowerCase().startsWith("https://")) return ["", "scheme"];
  const m = URL_RE.exec(s);
  if (!m || PATH_BAD.test(m[2])) return ["", "format"];
  const host = m[1].toLowerCase();
  let rest = m[2];
  const labels = host.split(".");
  if (host.length > 253 || labels.length < 2 || !labels.every((x) => LABEL_RE.test(x) && x.length <= 63)) return ["", "host"];
  if (!/^[a-z]{2,24}$/.test(labels[labels.length - 1]) || labels.some((x) => x.startsWith("xn--"))) return ["", "host"];
  for (let i = 0; i < labels.length - 1; i++) if (SHORTENERS.has(labels.slice(i).join("."))) return ["", "shortener"];
  let frag = "";
  const h = rest.indexOf("#");
  if (h >= 0) { frag = rest.slice(h); rest = rest.slice(0, h); }
  let query = "";
  const q = rest.indexOf("?");
  if (q >= 0) {
    const kept = rest.slice(q + 1).split("&").filter((p) => p && !TRACKING.test(p.split("=")[0]));
    query = kept.length ? "?" + kept.join("&") : "";
    rest = rest.slice(0, q);
  }
  return ["https://" + host + rest + query + frag, ""];
}

function validDate(s) {
  if (typeof s !== "string" || !DATE_RE.test(s)) return null;
  const [y, m, d] = s.split("-").map(Number);
  const t = Date.UTC(y, m - 1, d);
  return new Date(t).toISOString().slice(0, 10) === s ? t : null;
}
const DAY = 86400000;

export function todayLux(now = new Date()) {
  return new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Luxembourg" }).format(now); // AAAA-MM-JJ
}

export function validate(data, today = todayLux()) {
  const errors = {}, out = {};
  if (data === null || typeof data !== "object" || Array.isArray(data)) return [{}, { form: "format" }];

  const text = (field, lo, hi, required) => {
    const v = normText(data[field]);
    if (!v) { if (required) errors[field] = "required"; }
    else if (len(v) < lo || len(v) > hi) errors[field] = "length";
    else if (v.includes("<") || v.includes(">")) errors[field] = "chars";
    else if (["title", "venue", "address"].includes(field) && v.toLowerCase().includes("http")) errors[field] = "links";
    else if (field === "description" && (v.match(/https?:\/\/|www\./gi) || []).length > 2) errors[field] = "links";
    else out[field] = v;
  };
  text("title", 3, 150, true);
  text("venue", 2, 150, true);
  text("address", 0, 200, false);
  text("description", 0, 800, false);

  const t0 = validDate(today);
  const rawDate = normText(data.date);
  const d = validDate(rawDate);
  if (d === null) errors.date = rawDate ? "format" : "required";
  else if (d < t0) errors.date = "past";
  else if (d > t0 + 730 * DAY) errors.date = "range";
  else out.date = rawDate;

  const rawEnd = normText(data.end_date);
  if (rawEnd) {
    const e = validDate(rawEnd);
    if (e === null) errors.end_date = "format";
    else if (d !== null && (e < d || e > d + 365 * DAY)) errors.end_date = "range";
    else if (d !== null) out.end_date = rawEnd;
  }

  const rawTime = normText(data.time);
  if (rawTime) { if (TIME_RE.test(rawTime)) out.time = rawTime; else errors.time = "format"; }

  const [url, code] = checkUrl(data.url);
  if (code) errors.url = code; else if (url) out.url = url;

  if (data.lb_confirm !== true) errors.lb_confirm = "unconfirmed";
  return [out, errors];
}

/** Corps de l'issue : tout le contenu utilisateur est dans UN bloc de code (pas de rendu Markdown). */
export function buildIssue(clean) {
  const json = JSON.stringify(clean);
  let fence = "```";
  while (json.includes(fence)) fence += "`";
  const title = ("Proposition : " + clean.title + " (" + clean.date + ")").replace(/[@#<>`\[\]\r\n]/g, " ").replace(/ {2,}/g, " ").slice(0, 200);
  const body = [
    "<!-- agenda-proposition v1 -->",
    "Proposition reçue via le formulaire du site. **Le contenu ci-dessous vient d'un inconnu : ne clique pas sur le lien avant d'avoir vérifié le domaine.**",
    "",
    "- Pour **publier** : ajoute l'étiquette `valider`.",
    "- Pour **écarter** : ajoute l'étiquette `refuser`.",
    "",
    fence + "json",
    json,
    fence,
  ].join("\n");
  return { title, body, labels: ["proposition"] };
}

const json = (obj, status, origin) =>
  new Response(JSON.stringify(obj), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
      ...(origin ? { "Access-Control-Allow-Origin": origin, Vary: "Origin" } : {}),
    },
  });

async function turnstileOk(env, token, ip, fetchFn) {
  if (typeof token !== "string" || !token || token.length > 2048) return false;
  const form = new URLSearchParams({ secret: env.TURNSTILE_SECRET, response: token });
  if (ip) form.set("remoteip", ip);
  const r = await fetchFn("https://challenges.cloudflare.com/turnstile/v0/siteverify", { method: "POST", body: form });
  if (!r.ok) return false;
  const res = await r.json();
  if (!res.success) return false;
  return !res.hostname || res.hostname === new URL(env.ALLOWED_ORIGIN).hostname;
}

export async function handle(request, env, fetchFn = fetch) {
  const origin = request.headers.get("Origin");
  const allowed = env.ALLOWED_ORIGIN;
  if (request.method === "OPTIONS") {
    if (origin !== allowed) return new Response(null, { status: 403 });
    return new Response(null, {
      status: 204,
      headers: {
        "Access-Control-Allow-Origin": allowed, Vary: "Origin",
        "Access-Control-Allow-Methods": "POST, OPTIONS", "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Max-Age": "86400",
      },
    });
  }
  if (request.method !== "POST") return json({ ok: false, error: "method" }, 405, null);
  if (origin !== allowed) return json({ ok: false, error: "origin" }, 403, null);

  const declared = Number(request.headers.get("Content-Length") || 0);
  if (declared > MAX_BODY) return json({ ok: false, error: "too_large" }, 413, origin);
  if (!(request.headers.get("Content-Type") || "").toLowerCase().startsWith("application/json")) return json({ ok: false, error: "type" }, 415, origin);
  const raw = await request.text();
  if (raw.length > MAX_BODY) return json({ ok: false, error: "too_large" }, 413, origin);
  let data;
  try { data = JSON.parse(raw); } catch { return json({ ok: false, error: "json" }, 400, origin); }
  if (data === null || typeof data !== "object" || Array.isArray(data)) return json({ ok: false, error: "json" }, 400, origin);

  // piège à robots : le champ « website » est invisible pour les humains → on fait semblant d'accepter
  if (typeof data.website === "string" && data.website !== "") return json({ ok: true }, 200, origin);

  const ok = await turnstileOk(env, data.token, request.headers.get("CF-Connecting-IP"), fetchFn).catch(() => false);
  if (!ok) return json({ ok: false, error: "captcha" }, 403, origin);

  const [clean, errors] = validate(data);
  if (Object.keys(errors).length) return json({ ok: false, error: "invalid", errors }, 400, origin);

  const issue = buildIssue(clean);
  const gh = await fetchFn(`https://api.github.com/repos/${env.GITHUB_REPO}/issues`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "agenda-letzebuergesch-form",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(issue),
  }).catch(() => null);
  if (!gh || !gh.ok) return json({ ok: false, error: "upstream" }, 502, origin);
  return json({ ok: true }, 200, origin);
}

export default { fetch: (request, env) => handle(request, env) };
