"""Scraper pour une API REST WordPress (/wp-json/wp/v2/events) avec champs `meta`.

Format vérifié sur uni.lu : meta.event_start_date, meta.event_end_date,
meta.event_location, event_street, event_zip_code, event_city.
Les noms de champs peuvent être surchargés dans sources.json via "fields".
"""
import json
from common import fetch, make_event, parse_dt

DEFAULT_FIELDS = {
    "start": "event_start_date",
    "end": "event_end_date",
    "venue": "event_location",
    "street": "event_street",
    "zip": "event_zip_code",
    "city": "event_city",
}


def parse_items(items, source_name, fields):
    events = []
    for it in items:
        meta = it.get("meta") or {}
        start = parse_dt(str(meta.get(fields["start"], "")))
        title = (it.get("title") or {}).get("rendered", "")
        if not start or not title:
            continue
        address = " ".join(str(meta.get(fields[k], "") or "") for k in ("street", "zip", "city")).strip()
        events.append(make_event(
            source_name, title, start,
            end=parse_dt(str(meta.get(fields["end"], ""))),
            venue=str(meta.get(fields["venue"], "") or ""),
            address=address,
            description=(it.get("excerpt") or {}).get("rendered", "") or (it.get("content") or {}).get("rendered", ""),
            url=it.get("link", ""),
        ))
    return events


def scrape(source):
    fields = {**DEFAULT_FIELDS, **source.get("fields", {})}
    data = json.loads(fetch(source["url"]))
    if isinstance(data, dict):  # erreur WordPress renvoyée sous forme d'objet
        raise ValueError(data.get("message", "réponse inattendue"))
    return parse_items(data, source["name"], fields)
