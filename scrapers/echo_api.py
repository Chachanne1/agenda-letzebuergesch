"""Scraper pour l'API officielle d'ECHO (https://api.echo.lu/v1/), documentation v1.1.0.

Lit GET /allExperiences (expériences publiées, pagination obligatoire, 100 par page au maximum).
Chaque expérience déclare ses langues (`languages`: lb, fr, de, en…) : si « lb » en fait partie,
l'événement est confirmé directement, sans passer par la détection dans le texte.

La clé API (en-tête `api-key`) n'est JAMAIS écrite dans le dépôt : elle est lue dans la variable
d'environnement ECHO_API_KEY (secret GitHub du même nom, passé par le workflow).

Configuration dans sources.json :
  {"type": "echo_api", "url": "https://api.echo.lu/v1/allExperiences", "key_env": "ECHO_API_KEY",
   "per_page": 100, "max_pages": 30, "delay": 0.5}

Limites connues (à revoir avec de vraies réponses) :
  - l'API ne fournit pas l'adresse de la fiche publique : le lien « Méi Infos » utilise le site web
    du contact, sinon le lien de billetterie, sinon le lien en ligne ;
  - un événement récurrent (rrule) est affiché comme une période (début → fin), pas jour par jour ;
  - les expériences « permanentes » (horaires d'ouverture, sans date) sont ignorées.
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

from common import clean, USER_AGENT, make_event

try:
    from zoneinfo import ZoneInfo
    LUX = ZoneInfo("Europe/Luxembourg")
except Exception:  # pas de base de fuseaux (ex. Windows sans tzdata) : règle européenne codée en dur
    LUX = None

SKIP_STATUS = {"cancelled", "canceled", "postponed", "draft", "pending", "rejected"}


def _last_sunday(year, month):
    d = date(year, month, 31 if month in (3, 10) else 30)
    return d - timedelta(days=(d.weekday() + 1) % 7)


def to_local(value):
    """'2026-12-30T18:00:00Z' -> '2026-12-30T19:00' (heure du Luxembourg, comme sur ECHO)."""
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    if LUX is not None:
        local = dt.astimezone(LUX)
    else:
        y = dt.year
        dst_start = datetime(y, 3, _last_sunday(y, 3).day, 1, tzinfo=timezone.utc)
        dst_end = datetime(y, 10, _last_sunday(y, 10).day, 1, tzinfo=timezone.utc)
        local = dt + timedelta(hours=2 if dst_start <= dt < dst_end else 1)
    return local.strftime("%Y-%m-%dT%H:%M")


def as_text(content):
    """Le champ `description` peut être une chaîne ou un objet (une entrée par langue)."""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        # une entrée par langue : on n'en garde qu'une (luxembourgeois d'abord), sinon le titre est répété 3 fois
        for lang in ("lb", "lu", "ltz", "de", "fr", "en"):
            text = as_text(content.get(lang))
            if text.strip():
                return text
        return " ".join(as_text(v) for v in content.values())
    if isinstance(content, list):
        return " ".join(as_text(v) for v in content)
    return ""


def address_of(rec):
    addr = ((rec.get("location") or {}).get("address")) or {}
    if not addr:
        for v in rec.get("venues") or []:
            if isinstance(v, dict) and ((v.get("location") or {}).get("address")):
                addr = v["location"]["address"]
                break
    street = " ".join(str(addr.get(k) or "") for k in ("street", "number")).strip()
    town = " ".join(str(addr.get(k) or "") for k in ("postcode", "town")).strip()
    return ", ".join(p for p in (street, town) if p)


def venue_of(rec):
    for v in rec.get("venues") or []:
        if isinstance(v, dict) and v.get("title"):
            return as_text(v["title"]).strip()
    return ""


def link_of(rec):
    contact = rec.get("contact") or {}
    for url in (contact.get("website"), rec.get("purchaseLink"), rec.get("onlineLink")):
        if isinstance(url, str) and url.startswith(("http://", "https://")):
            return url
    return ""


def parse_record(rec, source_name):
    status = rec.get("status")
    current = (status.get("current") if isinstance(status, dict) else status) or ""
    if str(current).lower() in SKIP_STATUS:
        return []
    title = as_text(rec.get("title")).strip()
    if not title:
        return []
    langs = [str(l).lower() for l in (rec.get("languages") or [])]
    explicit = "lb" if "lb" in langs else ""
    description = " ".join(p for p in (as_text(rec.get("subtitle")), as_text(rec.get("description"))) if p)
    lt = rec.get("luxembourgTickets")
    tickets = isinstance(lt, dict) and bool(lt.get("publishOnEventim"))
    out = []
    for d in (rec.get("dates") or [])[:25]:
        if not isinstance(d, dict) or not d.get("from"):  # « permanent » : pas de date
            continue
        start, end = to_local(d.get("from")), to_local(d.get("to"))
        if not start:
            continue
        out.append(make_event(
            source_name, title, start, end="" if end == start else end,
            venue=venue_of(rec), address=address_of(rec), description=description,
            url=link_of(rec), explicit_lang=explicit,
        ))
        ev = out[-1]
        ev["description"] = clean(description, 2000)  # licence ECHO : fiche reprise le plus complètement possible
        ev["echo"] = True                              # affiche « Source : ECHO » + logo sur le site
        if tickets:
            ev["lt"] = True                            # « Billets disponibles avec luxembourgticket »
    return out


def get_json(url, key, retries=1):
    req = urllib.request.Request(url, headers={"Accept": "application/json", "api-key": key,
                                               "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 429 and retries:
            time.sleep(min(int(exc.headers.get("Retry-After", "30") or 30), 120))
            return get_json(url, key, retries - 1)
        if exc.code in (401, 403):
            raise ValueError(f"clé API refusée (HTTP {exc.code}) : vérifier le secret ECHO_API_KEY") from exc
        raise


def scrape(source):
    key = os.environ.get(source.get("key_env", "ECHO_API_KEY"), "").strip()
    if not key:
        raise ValueError(f"clé absente : définir la variable d'environnement {source.get('key_env', 'ECHO_API_KEY')}")
    base = source.get("url", "https://api.echo.lu/v1/allExperiences")
    per_page = min(int(source.get("per_page", 100)), 100)
    max_pages = int(source.get("max_pages", 30))
    delay = float(source.get("delay", 0.5))
    today = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00Z")

    events, seen_ids, pages, total = [], set(), 0, 0
    first, use_date = 0, True  # l'API pourrait numéroter les pages dès 1 ou refuser le filtre de date : on s'adapte
    page = first
    while pages < max_pages:
        params = {"pagination[page]": page, "pagination[perPage]": per_page}
        if use_date:
            params["date[from]"] = today + "T00:00:00Z"  # RFC 3339 exigé (pas une simple date)
        try:
            data = get_json(f"{base}?{urllib.parse.urlencode(params)}", key)
        except urllib.error.HTTPError as exc:
            if exc.code == 400 and use_date:
                print("[echo_api] filtre date[from] refusé : relance sans filtre (les passés sont écartés ensuite)")
                use_date = False
                continue
            raise
        records = data.get("records") if isinstance(data, dict) else None
        if not records:
            if page == 0 and pages == 0:  # numérotation à partir de 1 ?
                page = first = 1
                continue
            break
        pages += 1
        total += len(records)
        new = 0
        for rec in records:
            rid = rec.get("id")
            if rid in seen_ids:
                continue
            seen_ids.add(rid)
            new += 1
            events.extend(parse_record(rec, source["name"]))
        if new == 0 or len(records) < per_page:  # dernière page (ou l'API rejoue la même page)
            break
        page += 1
        time.sleep(delay)
    print(f"[echo_api] {pages} pages, {total} expériences, {len(events)} événements")
    if total == 0:
        raise ValueError("l'API n'a renvoyé aucune expérience")
    return events
