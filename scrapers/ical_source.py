"""Scraper générique pour un flux iCal (.ics). Sans dépendance externe."""
import re
from common import fetch, make_event, parse_dt


def _unfold(text):
    return re.sub(r"\r?\n[ \t]", "", text)


def _unescape(v):
    return v.replace("\\n", " ").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")


def parse_ics(text, source_name):
    events = []
    for block in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", _unfold(text), flags=re.S):
        props = {}
        for line in block.strip().splitlines():
            if ":" not in line:
                continue
            key, _, val = line.partition(":")
            props[key.split(";")[0].upper()] = _unescape(val.strip())
        start = parse_dt(props.get("DTSTART", ""))
        if not start or not props.get("SUMMARY"):
            continue
        events.append(make_event(
            source_name,
            props["SUMMARY"],
            start,
            end=parse_dt(props.get("DTEND", "")),
            venue=props.get("LOCATION", ""),
            description=props.get("DESCRIPTION", ""),
            url=props.get("URL", ""),
            explicit_lang=props.get("X-LANGUAGE", ""),
        ))
    return events


def scrape(source):
    return parse_ics(fetch(source["url"]), source["name"])
