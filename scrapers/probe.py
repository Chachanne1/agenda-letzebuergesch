"""Diagnostic : teste des URLs et indique quel format exploitable chaque site offre.

Usage :
    python scrapers/probe.py                       # teste toutes les URLs de sources.json
    python scrapers/probe.py https://site1 https://site2
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = "agenda-letzebuergesch/0.1 (+https://github.com/Chachanne1/agenda-letzebuergesch)"


def probe(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read(1_500_000).decode("utf-8", errors="replace")
            ctype = r.headers.get("Content-Type", "")
            status = r.status
    except Exception as exc:
        return f"ERREUR  {url}\n        {type(exc).__name__}: {exc}"
    found = []
    if "BEGIN:VCALENDAR" in body:
        found.append(f"iCal ({body.count('BEGIN:VEVENT')} VEVENT)")
    if re.search(r'application/ld\+json', body) and re.search(r'"@type"\s*:\s*"?\[?"?\w*Event', body):
        found.append("JSON-LD Event")
    if re.search(r"<rss|<feed", body[:2000], re.I):
        found.append("flux RSS/Atom")
    if "wp-json" in body:
        found.append("API WordPress (wp-json)")
    if body.lstrip().startswith(("{", "[")):
        found.append("JSON")
    for m in sorted(set(re.findall(r'href="([^"]+\.ics[^"]*)"', body)))[:3]:
        found.append(f"lien .ics: {m}")
    for m in sorted(set(re.findall(r'(?:type="application/(?:rss|atom)\+xml"[^>]*href="([^"]+)")', body)))[:3]:
        found.append(f"lien flux: {m}")
    verdict = ", ".join(found) if found else "aucun format structuré détecté (HTML seul)"
    return f"HTTP {status}  {url}\n        {ctype.split(';')[0]} | {len(body)//1024} Ko | {verdict}"


def main():
    urls = sys.argv[1:]
    if not urls:
        for s in json.loads((ROOT / "sources.json").read_text(encoding="utf-8")):
            urls += s.get("urls") or [s["url"]]
        txt = ROOT / "urls.txt"
        if txt.exists():
            for line in txt.read_text(encoding="utf-8").splitlines():
                line = line.split("#")[0].strip()
                if line.startswith("http"):
                    urls.append(line)
        urls = [u for u in urls if "exemple.lu" not in u]
    for u in urls:
        print(probe(u))


if __name__ == "__main__":
    main()
