"""Outils communs : schéma d'événement, téléchargement, détection du luxembourgeois."""
import hashlib
import html
import re
import unicodedata
import urllib.request
from datetime import datetime, timezone

USER_AGENT = "agenda-letzebuergesch/0.1 (+https://github.com/Chachanne1/agenda-letzebuergesch)"


def fetch(url, timeout=30):
    """Télécharge une URL et renvoie le texte (UTF-8)."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        charset = resp.headers.get_content_charset() or "utf-8"
    return raw.decode(charset, errors="replace")


def clean(text, limit=400):
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def normalize(text):
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def event_id(title, start, venue):
    key = f"{normalize(title)}|{(start or '')[:10]}|{normalize(venue)}"
    return hashlib.sha1(key.encode()).hexdigest()[:12]


def make_event(source_name, title, start, end="", venue="", address="",
               description="", url="", explicit_lang=""):
    """Construit un événement au schéma commun (sans statut de langue)."""
    return {
        "id": event_id(title, start, venue),
        "title": clean(title, 200),
        "start": start,
        "end": end or "",
        "venue": clean(venue, 150),
        "address": clean(address, 200),
        "description": clean(description, 400),
        "url": url,
        "source": source_name,
        "_lang": (explicit_lang or "").lower(),
    }


# --- Détection du luxembourgeois -------------------------------------------

STRONG_PATTERNS = [
    r"op l[eë]tz[eë]buergesch",
    r"\bin luxembourgish\b",
    r"\ben luxembourgeois\b",
    r"\bauf luxemburgisch\b",
    r"\bin luxemburgischer sprache\b",
    r"sprooch\s*:\s*l[eë]tz[eë]buergesch",
    r"langue\s*:\s*luxembourgeois",
    r"language\s*:\s*luxembourgish",
]
WEAK_PATTERNS = [r"l[eë]tz[eë]buerg(esch|er)", r"luxembourgish", r"luxemburgisch", r"luxembourgeois"]

# mots fonctionnels fréquents en luxembourgeois (et rares dans les autres langues)
LB_WORDS = {
    "déi", "dat", "wat", "och", "awer", "fir", "mat", "vun", "nët", "net", "ass", "sinn",
    "eng", "een", "den", "dem", "um", "am", "ëm", "ëmmer", "hunn", "kënnt", "kommt",
    "gëtt", "wëllt", "mir", "dir", "si", "hien", "se", "wann", "wéi", "iwwer", "bei",
    "duerch", "Lëtzebuerg", "haut", "muer", "owes", "méi", "ganz", "alleguer",
}
LB_DISTINCTIVE = {"déi", "awer", "fir", "nët", "och", "ëm", "ëmmer", "hunn", "gëtt", "wéi", "iwwer", "mir", "dir", "haut", "muer", "owes", "alleguer", "duerch"}


def detect_lb(title, description, explicit_lang="", lb_only_source=False):
    """Renvoie (statut, raison). statut ∈ {'confirmé', 'probable', None}.

    None = aucun indice de luxembourgeois : l'événement est écarté.
    """
    if lb_only_source:
        return "confirmé", "source dédiée au luxembourgeois"
    if explicit_lang in ("lb", "ltz", "lu", "luxembourgish", "letzebuergesch", "lëtzebuergesch"):
        return "confirmé", "langue indiquée par la source"
    text = f"{title} {description}".lower()
    for pat in STRONG_PATTERNS:
        if re.search(pat, text):
            return "confirmé", "mention explicite dans le texte"
    words = re.findall(r"[a-zäöüéèëêàç]+", text)
    hits = sum(1 for w in words if w in LB_DISTINCTIVE)
    if hits >= 3:
        return "probable", f"texte semble en luxembourgeois ({hits} mots typiques)"
    for pat in WEAK_PATTERNS:
        if re.search(pat, text):
            return "probable", "mention de la langue/du pays dans le texte"
    return None, ""


def parse_dt(value):
    """Parse une date ISO ou iCal simple -> chaîne ISO 'YYYY-MM-DDTHH:MM' ou 'YYYY-MM-DD'."""
    if not value:
        return ""
    v = value.strip()
    m = re.match(r"^(\d{4})(\d{2})(\d{2})(?:T(\d{2})(\d{2})(\d{2})?)?Z?$", v)
    if m:
        y, mo, d, h, mi, _ = m.groups()
        return f"{y}-{mo}-{d}T{h}:{mi}" if h else f"{y}-{mo}-{d}"
    m = re.match(r"^(\d{4}-\d{2}-\d{2})(?:[T ](\d{2}:\d{2}))?", v)
    if m:
        return f"{m.group(1)}T{m.group(2)}" if m.group(2) else m.group(1)
    return ""


def today_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")
