"""Scraper HTML pour les sites alimentés par ECHO (echo.lu) : visitluxembourg.com,
visitguttland.lu, visit-eislek.lu, visitminett.lu, mullerthal.lu…

Principe : on part de pages de liste (« seeds »), on suit leur pagination, on relève
les liens d'événements, puis on lit chaque fiche (titre, dates, lieu, description).
La langue est ensuite détectée par run.py dans titre + description.

Configuration dans sources.json :
  {"type": "echo_html", "urls": ["https://www.visitluxembourg.com/fr/agenda"],
   "max_list_pages": 15, "max_events": 250, "delay": 1.0}
"""
import html as htmllib
import re
import time
from datetime import date, timedelta
from urllib.parse import urljoin, urlparse

from common import fetch, make_event

EVENT_PATH = re.compile(r"/(?:evenement|event|veranstaltung|evenementen)/[^/?#]+$")
DATE_RE = re.compile(r"\b(\d{2})\.(\d{2})\.(20\d{2})\s*(\d{2}:\d{2})?")
HEAD_DATES = re.compile(r"^(die nächsten termine|next events|dates des prochains événements|"
                        r"volgende termijnen|prochaines dates|nächste termine)$", re.I)
HEAD_PLACE = re.compile(r"^(veranstaltungsort|location|lieu|locatie)$", re.I)
WHERE = re.compile(r"^(wo|where|où|waar)\s*\?", re.I)
ADDR = re.compile(r"^(adresse|address|adres)\s*:?$", re.I)
MAPLINK = re.compile(r"^(auf karte anzeigen|show on map|afficher sur la carte|op kaart tonen)$", re.I)


def to_text_lines(page):
    page = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", "", page, flags=re.S | re.I)
    page = re.sub(r"<[^>]+>", "\n", page)
    page = htmllib.unescape(page).replace("\xad", "").replace("​", "")
    lines = [re.sub(r"\s+", " ", l).strip() for l in page.split("\n")]
    return [l for l in lines if l]


def meta(page, prop):
    m = re.search(rf'<meta[^>]+(?:property|name)="{prop}"[^>]+content="([^"]*)"', page)
    return htmllib.unescape(m.group(1)).strip() if m else ""


def find_links(page, base):
    """Renvoie (liens d'événements, liens de pagination)."""
    events, pages = [], []
    for href in re.findall(r'href="([^"]+)"', page):
        url = urljoin(base, htmllib.unescape(href)).split("#")[0]
        path = urlparse(url).path
        if EVENT_PATH.search(path):
            if url not in events:
                events.append(url)
        elif "cHash=" in url and re.search(r"[?&]page=\d+", url):
            if url not in pages:
                pages.append(url)
    return events, pages


def parse_detail(page, url, source_name):
    """Lit une fiche d'événement. Renvoie une liste d'événements (un par date à venir)."""
    title = meta(page, "og:title") or ""
    title = re.sub(r"\s*[-–|]\s*(Visit\s+\w+|visit\w+)\s*$", "", title).strip()
    if not title:
        return []
    lines = to_text_lines(page)

    # dates : bloc « Prochaines dates » ; à défaut, ligne « Quand ? »
    dates = []
    for i, l in enumerate(lines):
        if HEAD_DATES.match(l):
            block = []
            for j in range(i + 1, min(i + 40, len(lines))):
                if HEAD_PLACE.match(lines[j]):
                    break
                block.append(lines[j])
            for m in DATE_RE.finditer(" ".join(block)):
                d, mo, y, t = m.groups()
                dates.append(f"{y}-{mo}-{d}" + (f"T{t}" if t else ""))
            break
    if not dates:
        for i, l in enumerate(lines):
            if re.match(r"^(wann|when|quand|wanneer)\s*\?", l, re.I):
                m = DATE_RE.search(" ".join(lines[i:i + 3]))
                if m:
                    d, mo, y, t = m.groups()
                    dates.append(f"{y}-{mo}-{d}" + (f"T{t}" if t else ""))
                break
    if not dates:
        return []

    # lieu
    venue = address = ""
    for i, l in enumerate(lines):
        if ADDR.match(l) or re.match(r"^(adresse|address|adres)\s*:\s*\S", l, re.I):
            first = re.sub(r"^[^:]*:\s*", "", l) if ":" in l and len(l) > 10 else ""
            rest = []
            for j in range(i + 1, min(i + 6, len(lines))):
                if MAPLINK.match(lines[j]) or re.match(r"^(tel|phone|téléphone)", lines[j], re.I):
                    break
                rest.append(lines[j])
            parts = ([first] if first else []) + rest
            if parts:
                venue, address = parts[0], ", ".join(parts[1:])
            break
    if not venue:
        for l in lines:
            if WHERE.match(l):
                venue = re.sub(r"^[^?]*\?\s*", "", l)
                break

    # description : entre la ligne « Où ? » (+ catégorie) et le pied « © echo.lu »
    desc_parts = []
    for i, l in enumerate(lines):
        if WHERE.match(l):
            j = i + 2  # saute la catégorie
            if j < len(lines) and lines[j] == title:
                j += 1
            while j < len(lines) and lines[j] not in ("©", "©echo.lu") and len(desc_parts) < 40:
                if lines[j] != ".":
                    desc_parts.append(lines[j])
                j += 1
            break
    description = " ".join(desc_parts) or meta(page, "og:description")

    out = []
    for start, end in merge_dates(dates)[:25]:
        out.append(make_event(source_name, title, start, end=end, venue=venue, address=address,
                              description=description, url=url))
    return out


def merge_dates(dates):
    """Regroupe les jours consécutifs (expositions…) en une seule période (début, fin)."""
    items = sorted(set(dates))
    runs = []
    for d in items:
        day, _, hour = d.partition("T")
        cur = date.fromisoformat(day)
        if runs:
            last_day, last_hour, first = runs[-1]
            if cur == last_day + timedelta(days=1) and hour == last_hour:
                runs[-1] = (cur, hour, first)
                continue
        runs.append((cur, hour, d))
    out = []
    for last_day, hour, first in runs:
        end = last_day.isoformat() + (f"T{hour}" if hour else "")
        out.append((first, end if end != first else None))
    return out


def scrape(source):
    name = source["name"]
    delay = float(source.get("delay", 1.0))
    max_lists = int(source.get("max_list_pages", 15))
    max_events = int(source.get("max_events", 250))

    event_urls, queue, seen_lists = [], list(source.get("urls", [])), set()
    while queue and len(seen_lists) < max_lists:
        url = queue.pop(0)
        if url in seen_lists:
            continue
        seen_lists.add(url)
        try:
            page = fetch(url)
        except Exception as exc:
            print(f"[echo] liste en échec {url[-60:]} : {type(exc).__name__}: {exc}")
            continue
        evs, pgs = find_links(page, url)
        print(f"[echo] liste {len(seen_lists)} : {len(page)} car., {len(evs)} fiches, {len(pgs)} liens de page")
        for e in evs:
            if e not in event_urls:
                event_urls.append(e)
        queue.extend(p for p in pgs if p not in seen_lists)
        time.sleep(delay)

    events, nodate, failed = [], 0, 0
    for url in event_urls[:max_events]:
        try:
            got = parse_detail(fetch(url), url, name)
            events.extend(got)
            nodate += 0 if got else 1
        except Exception:
            failed += 1  # une fiche en échec ne bloque pas les autres
        time.sleep(delay)
    print(f"[echo] {len(seen_lists)} pages de liste, {len(event_urls)} fiches, "
          f"{len(events)} événements, {nodate} sans date, {failed} en échec")
    if not event_urls:
        raise ValueError("aucun lien d'événement trouvé dans les pages de liste")
    return events
