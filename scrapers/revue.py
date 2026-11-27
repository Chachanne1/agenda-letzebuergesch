"""Listes de revue des événements ECHO, gérées par des issues GitHub (cases à cocher).

  python scrapers/revue.py publish   crée/met à jour deux issues d'après data/revue_queue.json (workflow update.yml)
  python scrapers/revue.py apply     lit les cases cochées (corps de l'issue dans $ISSUE_BODY, étiquette dans
                                     $ISSUE_LABELS) et les enregistre dans data/revue.json (workflow revue.yml)

Liste 1 « verifier » : affichée sur le site ; cocher = RETIRER (faux positif : texte « en luxembourgeois » mais lb non déclaré).
Liste 2 « sauver »   : NON affichée ; cocher = AJOUTER (lb déclaré mais rien dans le texte ne l'indique).
Ne pas cocher = rien ne change : le site continue de se mettre à jour sans intervention.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OWNER = os.environ.get("REVUE_OWNER", "Chachanne1")
MAX_ITEMS = 100
VERSION = "<!--v3-->"  # change quand le format de l'issue change : force la réécriture des issues existantes
LISTS = {
    "verifier": {
        "label": "revue-verifier", "decision": "retirer",
        "title": "À vérifier : activités affichées dont le texte dit « en luxembourgeois »",
        "intro": "Ces activités **sont affichées** sur le site. Le texte mentionne le luxembourgeois mais l'organisateur n'a pas "
                 "coché « lb ». **Cochez celles qui sont des faux positifs** : elles seront retirées au prochain passage. "
                 "Ne rien cocher = elles restent affichées. « écarter définitivement » : l'activité disparaît de cette liste pour de bon.",
    },
    "sauver": {
        "label": "revue-sauver", "decision": "ajouter",
        "title": "À rattraper : activités « lb » déclaré mais rien dans le texte (non affichées)",
        "intro": "Ces activités **ne sont pas affichées**. L'organisateur a coché « lb » mais le texte ne le confirme pas. "
                 "**Cochez celles à ajouter** au site. Ne rien cocher = elles restent masquées.",
    },
}
ID_RE = re.compile(r"^- \[( |x|X)\] <!--id:([0-9a-f]{12})-->", re.M)
ALL_RE = re.compile(r"^- \[(x|X)\] <!--all-->", re.M)
NO_RE = re.compile(r"^\s+- \[( |x|X)\] <!--no:([0-9a-f]{12})-->", re.M)


def gh(*args, check=True):
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=check)


def line(it):
    when = (it.get("start") or "")[:16].replace("T", " ")
    if it.get("end") and it["end"][:10] != (it.get("start") or "")[:10]:
        when += " → " + it["end"][:10]
    bits = [f"**{it['title']}**", when, it.get("venue") or "", it.get("reason") or ""]
    txt = f"- [ ] <!--id:{it['id']}--> " + " · ".join(b for b in bits if b)
    if it.get("url"):
        txt += f" · [fiche]({it['url']})"
    if it.get("snippet"):
        snippet = re.sub(r"\s+", " ", it["snippet"])
        txt += f"\n  > {snippet}…"
    return txt + f"\n  - [ ] <!--no:{it['id']}--> écarter définitivement"


def body_for(kind, items, ticked=(), ticked_no=()):
    cfg = LISTS[kind]
    shown = items[:MAX_ITEMS]
    rows = []
    for it in shown:
        row = line(it)
        if it["id"] in ticked:
            row = row.replace("- [ ]", "- [x]", 1)
        if it["id"] in ticked_no:
            row = row.replace(f"- [ ] <!--no:{it['id']}-->", f"- [x] <!--no:{it['id']}-->")
        rows.append(row)
    more = f"\n\n_{len(items) - MAX_ITEMS} autres à venir au prochain passage._" if len(items) > MAX_ITEMS else ""
    master = ""
    if kind == "sauver":
        master = (f"- [ ] <!--all--> **Écarter TOUTE la liste d'un coup** ({len(items)} activités, y compris celles pas encore "
                  "affichées ci-dessous), sauf celles dont la case « ajouter » est cochée\n\n")
    return f"@{OWNER} {VERSION}\n\n{cfg['intro']}\n\n" + master + "\n".join(rows) + more + "\n"


def ids_in(body):
    return ID_RE.findall(body or "")


def publish():
    queue = json.loads((DATA / "revue_queue.json").read_text(encoding="utf-8"))
    for kind, cfg in LISTS.items():
        items = sorted(queue.get(kind, []), key=lambda i: i.get("start", ""))
        gh("label", "create", cfg["label"], "--color", "5319e7", "--description", "Revue des activités ECHO", check=False)
        res = gh("issue", "list", "--label", cfg["label"], "--state", "open", "--json", "number,body", "--limit", "1")
        existing = json.loads(res.stdout or "[]")
        if not items:
            if existing:
                gh("issue", "close", str(existing[0]["number"]), "--comment", "Liste vide : plus rien à vérifier.")
            continue
        if not existing:
            gh("issue", "create", "--title", cfg["title"], "--label", cfg["label"], "--assignee", OWNER,
               "--body", body_for(kind, items))
            print(f"[revue] issue créée ({kind}) : {len(items)} éléments")
            continue
        num, old = existing[0]["number"], existing[0]["body"]
        old_ids = [i for _, i in ids_in(old)]
        new_ids = [i["id"] for i in items[:MAX_ITEMS]]
        if old_ids == new_ids and VERSION in (old or ""):
            continue  # rien de changé : on ne touche pas à l'issue (les cases cochées en cours restent)
        ticked = {i for mark, i in ids_in(old) if mark.lower() == "x"}
        ticked_no = {i for mark, i in NO_RE.findall(old or "") if mark.lower() == "x"}
        gh("issue", "edit", str(num), "--body", body_for(kind, items, ticked, ticked_no))
        added = [i for i in new_ids if i not in old_ids]
        if added:
            gh("issue", "comment", str(num), "--body", f"@{OWNER} {len(added)} nouvel(le)s activité(s) à examiner.")
        print(f"[revue] issue #{num} mise à jour ({kind}) : {len(items)} éléments, {len(added)} nouveaux")


def apply():
    labels = os.environ.get("ISSUE_LABELS", "")
    kind = next((k for k, c in LISTS.items() if c["label"] in labels.split(",")), None)
    if not kind:
        print("[revue] issue sans étiquette de revue : rien à faire")
        return
    body = os.environ.get("ISSUE_BODY", "")
    ticked = [i for mark, i in ids_in(body) if mark.lower() == "x"]
    ticked_no = [i for mark, i in NO_RE.findall(body) if mark.lower() == "x"]
    all_ticked = bool(ALL_RE.search(body)) and kind == "sauver"
    if not ticked and not ticked_no and not all_ticked:
        print("[revue] aucune case cochée")
        return
    path = DATA / "revue.json"
    try:
        revue = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        revue = {}
    key = LISTS[kind]["decision"]
    out = {k: list(revue.get(k, [])) for k in ("retirer", "ajouter", "ecarter")}
    out[key] = sorted(set(out[key]) | (set(ticked) - set(ticked_no)))
    out["ecarter"] = sorted(set(out["ecarter"]) | set(ticked_no))
    if all_ticked:  # tout ce qui attend dans la file, sauf les « ajouter » cochés
        try:
            queue = json.loads((DATA / "revue_queue.json").read_text(encoding="utf-8")).get("sauver", [])
        except (FileNotFoundError, json.JSONDecodeError):
            queue = []
        rest = {q["id"] for q in queue} - set(ticked)
        out["ecarter"] = sorted(set(out["ecarter"]) | rest)
        print(f"[revue] liste entière écartée : {len(rest)} activités")
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[revue] {len(ticked)} décision(s) {key}, {len(ticked_no)} écartée(s) définitivement")


if __name__ == "__main__":
    {"publish": publish, "apply": apply}[sys.argv[1]]()
