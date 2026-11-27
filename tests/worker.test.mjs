// Tests du Worker : node --test tests/worker.test.mjs  (aucun accès réseau, fetch simulé)
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { validate, handle, buildIssue } from "../cloudflare/worker.js";

const spec = JSON.parse(readFileSync(new URL("./validation_cases.json", import.meta.url), "utf8"));

for (const c of spec.cases) {
  test("validation : " + c.name, () => {
    const [clean, errors] = validate(c.input, spec.today);
    assert.deepEqual(errors, c.errors);
    if (c.clean) assert.deepEqual(clean, c.clean);
  });
}

const ORIGIN = "https://chachanne1.github.io";
const env = { ALLOWED_ORIGIN: ORIGIN, GITHUB_REPO: "Chachanne1/agenda-letzebuergesch", GITHUB_TOKEN: "ghp_x", TURNSTILE_SECRET: "s" };
const future = new Date(Date.now() + 10 * 86400000).toISOString().slice(0, 10);
const good = { title: "Konferenz op Lëtzebuergesch", date: future, venue: "Rotondes", lb_confirm: true, token: "tok" };

function mkFetch({ captcha = true, gh = true } = {}) {
  const calls = [];
  const fn = async (url, init) => {
    calls.push({ url: String(url), init });
    if (String(url).includes("turnstile")) return new Response(JSON.stringify({ success: captcha, hostname: "chachanne1.github.io" }));
    return new Response("{}", { status: gh ? 201 : 500 });
  };
  fn.calls = calls;
  return fn;
}
const req = (body, headers = {}, method = "POST") =>
  new Request("https://w.example/", { method, headers: { Origin: ORIGIN, "Content-Type": "application/json", ...headers }, body: method === "POST" ? (typeof body === "string" ? body : JSON.stringify(body)) : undefined });

test("succès : crée l'issue avec l'étiquette proposition", async () => {
  const f = mkFetch();
  const r = await handle(req(good), env, f);
  assert.equal(r.status, 200);
  assert.equal(r.headers.get("Access-Control-Allow-Origin"), ORIGIN);
  const gh = f.calls.find((c) => c.url.includes("api.github.com"));
  assert.match(gh.url, /Chachanne1\/agenda-letzebuergesch\/issues$/);
  assert.equal(gh.init.headers.Authorization, "Bearer ghp_x");
  const issue = JSON.parse(gh.init.body);
  assert.deepEqual(issue.labels, ["proposition"]);
  assert.ok(!("token" in JSON.parse(issue.body.split("\n").find((l) => l.startsWith("{")))));
});
test("mauvaise origine refusée, sans appel réseau", async () => {
  const f = mkFetch();
  const r = await handle(req(good, { Origin: "https://evil.example" }), env, f);
  assert.equal(r.status, 403);
  assert.equal(f.calls.length, 0);
});
test("sans Origin refusé", async () => {
  const f = mkFetch();
  const r = await handle(new Request("https://w.example/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(good) }), env, f);
  assert.equal(r.status, 403);
});
test("préflight CORS", async () => {
  const r = await handle(req(null, {}, "OPTIONS"), env, mkFetch());
  assert.equal(r.status, 204);
  const bad = await handle(req(null, { Origin: "https://evil.example" }, "OPTIONS"), env, mkFetch());
  assert.equal(bad.status, 403);
});
test("GET refusé", async () => {
  assert.equal((await handle(req(null, {}, "GET"), env, mkFetch())).status, 405);
});
test("captcha invalide → 403, pas d'issue", async () => {
  const f = mkFetch({ captcha: false });
  const r = await handle(req(good), env, f);
  assert.equal(r.status, 403);
  assert.ok(!f.calls.some((c) => c.url.includes("api.github.com")));
});
test("piège à robots : faux succès, aucun appel", async () => {
  const f = mkFetch();
  const r = await handle(req({ ...good, website: "http://spam" }), env, f);
  assert.equal(r.status, 200);
  assert.equal(f.calls.length, 0);
});
test("données invalides → 400 avec codes", async () => {
  const f = mkFetch();
  const r = await handle(req({ ...good, url: "http://x.lu" }), env, f);
  assert.equal(r.status, 400);
  assert.deepEqual((await r.json()).errors, { url: "scheme" });
  assert.ok(!f.calls.some((c) => c.url.includes("api.github.com")));
});
test("corps trop gros, mauvais type, JSON cassé", async () => {
  const f = mkFetch();
  assert.equal((await handle(req("x".repeat(9000)), env, f)).status, 413);
  assert.equal((await handle(req(good, { "Content-Type": "text/plain" }), env, f)).status, 415);
  assert.equal((await handle(req("{pas json"), env, f)).status, 400);
});
test("GitHub en panne → 502 sans fuite d'information", async () => {
  const r = await handle(req(good), env, mkFetch({ gh: false }));
  assert.equal(r.status, 502);
  assert.deepEqual(await r.json(), { ok: false, error: "upstream" });
});
test("issue : titre assaini, contenu hostile enfermé dans le bloc de code", () => {
  const [clean] = validate({ title: "Salut @owner #1 [x](y) `z`", date: future, venue: "Xy", description: "``` fin du bloc ```\n@owner", lb_confirm: true });
  const issue = buildIssue(clean);
  assert.ok(!/[@#`\[\]]/.test(issue.title));
  const lines = issue.body.split("\n");
  const open = lines.findIndex((l) => /^`{3,}json$/.test(l));
  const fence = lines[open].slice(0, -4);
  assert.ok(fence.length >= 4, "fence plus longue que les ``` du contenu");
  assert.equal(lines[lines.length - 1], fence);
  assert.equal(lines.length - 1 - open, 2); // une seule ligne de JSON entre les deux fences
});
