"""Construit le dossier _site/ : copie le site, les données, et génère events.ics."""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "_site"


def ics_escape(s):
    return (s or "").replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", " ")


def ics_date(iso):
    if "T" in iso:
        return "DTSTART:" + iso.replace("-", "").replace(":", "") + "00"
    return "DTSTART;VALUE=DATE:" + iso.replace("-", "")


def build_ics(events):
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//agenda-letzebuergesch//LB//",
             "X-WR-CALNAME:Agenda Lëtzebuergesch"]
    for e in events:
        lines += ["BEGIN:VEVENT", f"UID:{e['id']}@agenda-letzebuergesch",
                  ics_date(e["start"]), f"SUMMARY:{ics_escape(e['title'])}",
                  f"LOCATION:{ics_escape(e.get('venue', ''))}"]
        if e.get("url"):
            lines.append(f"URL:{e['url']}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(ROOT / "site", OUT)
    (OUT / "data").mkdir(exist_ok=True)
    events = json.loads((ROOT / "data" / "events.json").read_text(encoding="utf-8"))
    (OUT / "data" / "events.json").write_text(json.dumps(events, ensure_ascii=False), encoding="utf-8")
    (OUT / "events.ics").write_text(build_ics(events), encoding="utf-8")
    print(f"Site construit dans {OUT} ({len(events)} événements)")


if __name__ == "__main__":
    main()
