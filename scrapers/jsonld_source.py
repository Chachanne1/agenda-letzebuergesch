"""Scraper générique : lit les blocs JSON-LD schema.org/Event d'une page web.

Beaucoup de sites culturels publient leurs événements ainsi. Une source peut
lister plusieurs pages (champ "urls") ou une seule ("url").
"""
import json
import re
from common import fetch, make_event, parse_dt


def _walk(node):
    if isinstance(node, list):
        for n in node:
            yield from _walk(n)
    elif isinstance(node, dict):
        types = node.get("@type")
        types = types if isinstance(types, list) else [types]
        if any(isinstance(t, str) and t.endswith("Event") for t in types):
            yield node
        for key in ("@graph", "itemListElement", "item"):
            if key in node:
                yield from _walk(node[key])


def _place(loc):
    if isinstance(loc, list):
        loc = loc[0] if loc else {}
    if isinstance(loc, dict):
        addr = loc.get("address", "")
        if isinstance(addr, dict):
            addr = " ".join(str(addr.get(k, "")) for k in ("streetAddress", "postalCode", "addressLocality"))
        return loc.get("name", ""), str(addr)
    return str(loc or ""), ""


def parse_page(html, source_name, page_url):
    events = []
    for raw in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html, flags=re.S | re.I):
        try:
            data = json.loads(raw.strip())
        except json.JSONDecodeError:
            continue
        for ev in _walk(data):
            start = parse_dt(str(ev.get("startDate", "")))
            name = ev.get("name")
            if not start or not name:
                continue
            venue, address = _place(ev.get("location"))
            lang = ev.get("inLanguage", "")
            if isinstance(lang, list):
                lang = lang[0] if lang else ""
            events.append(make_event(
                source_name, str(name), start,
                end=parse_dt(str(ev.get("endDate", ""))),
                venue=venue, address=address,
                description=str(ev.get("description", "")),
                url=str(ev.get("url") or page_url),
                explicit_lang=str(lang),
            ))
    return events


def scrape(source):
    urls = source.get("urls") or [source["url"]]
    out = []
    for url in urls:
        out.extend(parse_page(fetch(url), source["name"], url))
    return out
