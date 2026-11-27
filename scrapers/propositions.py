"""Propositions d'événements envoyées via le formulaire du site.

Chaîne : formulaire → Cloudflare Worker (cloudflare/worker.js) → issue GitHub « proposition »
→ (tu ajoutes l'étiquette « valider ») → workflow proposition.yml → ce script → data/events.json.

Ce fichier contient la validation de référence ; cloudflare/worker.js en a la copie JavaScript
(les deux sont testés avec les mêmes cas : tests/validation_cases.json).
Règle d'or : le contenu de l'issue est une DONNÉE. On ne le suit pas, on ne le télécharge pas,
on le revalide intégralement avant de l'écrire dans events.json.
"""
import json
import os
import re
import sys
import unicodedata
from datetime import date, timedelta
from pathlib import Path

from common import event_id, today_iso

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SOURCE_NAME = "Proposition (formulaire)"

SHORTENERS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd", "buff.ly", "cutt.ly", "rebrand.ly",
    "shorturl.at", "tiny.cc", "rb.gy", "lnkd.in", "t.ly", "s.id", "v.gd", "bl.ink", "shorte.st",
    "adf.ly", "tr.ee", "qr.ae", "urlz.fr", "lc.cx", "clck.ru", "x.co", "ift.tt", "dlvr.it",
}
TRACKING = re.compile(r"^(utm_.*|fbclid|gclid|dclid|msclkid|igshid|mc_cid|mc_eid|_hsenc|_hsmi|mkt_tok|yclid)$", re.I)
CONTROLS = re.compile("[\u0000-\u001f\u007f-\u009f\u00ad\u200b-\u200f\u202a-\u202e\u2060-\u2064\u2066-\u2069\ufeff]")
URL_RE = re.compile(r"^https://([a-z0-9.-]+)(?::443)?((?:[/?#][\x21-\x7e]*)?)$", re.I)
PATH_BAD = re.compile(r"[<>\"'`\\]")
LABEL_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def norm_text(value):
    """Texte sur une ligne : NFC, retours à la ligne → espace, caractères de contrôle/invisibles retirés."""
    if not isinstance(value, str):
        return ""
    s = unicodedata.normalize("NFC", value)
    s = re.sub("[\t\n\r   ]", " ", s)
    s = CONTROLS.sub("", s)
    return re.sub(" {2,}", " ", s).strip()


def check_url(raw):
    """Renvoie (url_nettoyée, code_erreur)."""
    s = norm_text(raw)
    if not s:
        return "", ""
    if len(s) > 300:
        return "", "length"
    if not s.lower().startswith("https://"):
        return "", "scheme"
    m = URL_RE.match(s)
    if not m or PATH_BAD.search(m.group(2)):
        return "", "format"
    host, rest = m.group(1).lower(), m.group(2)
    labels = host.split(".")
    if len(host) > 253 or len(labels) < 2 or not all(LABEL_RE.match(x) and len(x) <= 63 for x in labels):
        return "", "host"
    if not re.fullmatch(r"[a-z]{2,24}", labels[-1]) or any(x.startswith("xn--") for x in labels):
        return "", "host"
    if any(".".join(labels[i:]) in SHORTENERS for i in range(len(labels) - 1)):
        return "", "shortener"
    frag = ""
    if "#" in rest:
        rest, frag = rest.split("#", 1)
        frag = "#" + frag
    query = ""
    if "?" in rest:
        rest, query = rest.split("?", 1)
        kept = [p for p in query.split("&") if p and not TRACKING.match(p.split("=", 1)[0])]
        query = "?" + "&".join(kept) if kept else ""
    return "https://" + host + rest + query + frag, ""


def valid_date(s):
    if not isinstance(s, str) or not DATE_RE.match(s):
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def validate(data, today=None):
    """Valide une proposition. Renvoie (champs_nettoyés, erreurs{champ: code})."""
    today = today or today_iso()
    errors, out = {}, {}
    if not isinstance(data, dict):
        return {}, {"form": "format"}

    def text(field, lo, hi, required):
        v = norm_text(data.get(field))
        if not v:
            if required:
                errors[field] = "required"
        elif len(v) < lo or len(v) > hi:
            errors[field] = "length"
        elif "<" in v or ">" in v:
            errors[field] = "chars"
        elif field in ("title", "venue", "address") and "http" in v.lower():
            errors[field] = "links"
        elif field == "description" and len(re.findall(r"https?://|www\.", v, re.I)) > 2:
            errors[field] = "links"
        else:
            out[field] = v

    text("title", 3, 150, True)
    text("venue", 2, 150, True)
    text("address", 0, 200, False)
    text("description", 0, 800, False)

    t0 = date.fromisoformat(today)
    d = valid_date(norm_text(data.get("date")))
    if d is None:
        errors["date"] = "required" if not norm_text(data.get("date")) else "format"
    elif d < t0:
        errors["date"] = "past"
    elif d > t0 + timedelta(days=730):
        errors["date"] = "range"
    else:
        out["date"] = d.isoformat()

    raw_end = norm_text(data.get("end_date"))
    if raw_end:
        e = valid_date(raw_end)
        if e is None:
            errors["end_date"] = "format"
        elif d and (e < d or e > d + timedelta(days=365)):
            errors["end_date"] = "range"
        elif d:
            out["end_date"] = e.isoformat()

    raw_time = norm_text(data.get("time"))
    if raw_time:
        if TIME_RE.match(raw_time):
            out["time"] = raw_time
        else:
            errors["time"] = "format"

    url, code = check_url(data.get("url"))
    if code:
        errors["url"] = code
    elif url:
        out["url"] = url

    if data.get("lb_confirm") is not True:
        errors["lb_confirm"] = "unconfirmed"
    return out, errors


def to_event(c):
    """Champs nettoyés → événement au schéma commun (voir common.make_event)."""
    start = c["date"] + ("T" + c["time"] if c.get("time") else "")
    end = c.get("end_date", "")
    if end and c.get("time"):
        end += "T" + c["time"]
    return {
        "id": event_id(c["title"], start, c["venue"]),
        "title": c["title"], "start": start, "end": end,
        "venue": c["venue"], "address": c.get("address", ""),
        "description": c.get("description", ""), "url": c.get("url", ""),
        "source": SOURCE_NAME, "status": "confirmé", "reason": "proposé et validé",
        "proposed": True,
    }


FENCE_RE = re.compile(r"^(`{3,})json[ \t]*\r?\n(.*?)\r?\n\1[ \t]*$", re.M | re.S)


def parse_issue_body(body):
    """Extrait le JSON de la proposition (bloc de code balisé). Renvoie un dict ou None."""
    m = FENCE_RE.search(body or "")
    if not m:
        return None
    try:
        data = json.loads(m.group(2))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def add_to_events(event, events_path):
    """Ajoute l'événement s'il n'existe pas déjà. Renvoie 'added' ou 'duplicate'."""
    try:
        events = json.loads(events_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        events = []
    if any(e.get("id") == event["id"] for e in events):
        return "duplicate"
    events.append(event)
    events.sort(key=lambda e: e["start"])
    events_path.write_text(json.dumps(events, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return "added"


def set_output(key, value):
    path = os.environ.get("GITHUB_OUTPUT")
    line = f"{key}={str(value).replace(chr(10), ' ')}\n"
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line)
    print(line, end="")


def main():
    """Appelé par le workflow : lit l'événement GitHub (données, jamais interpolé dans un shell)."""
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    issue = event.get("issue") or {}
    labels = {l.get("name") for l in issue.get("labels", [])}
    if "proposition" not in labels:
        set_output("result", "ignored")
        return 0
    data = parse_issue_body(issue.get("body"))
    if data is None:
        set_output("result", "invalid")
        set_output("message", "Bloc JSON introuvable ou illisible.")
        return 0
    clean, errors = validate(data)
    if errors:
        set_output("result", "invalid")
        set_output("message", "Champs invalides : " + ", ".join(f"{k} ({v})" for k, v in errors.items()))
        return 0
    ev = to_event(clean)
    set_output("result", add_to_events(ev, DATA / "events.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
