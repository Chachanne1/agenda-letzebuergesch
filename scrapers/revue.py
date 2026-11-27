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
MAX_ITEMS = 150
LISTS = {
    "verifier": {
        "label": "revue-verifier", "decision": "retirer",
        "title": "À vérifier : activités affichées dont le texte dit « en luxembourgeois »",
        "intro": "Ces activités **sont affichées** sur le site. Le texte mentionne le luxembourgeois mais l'organisateur n'a pas "
                 "coché « lb ». **Cochez celles qui sont des faux positifs** : elles seront retirées au prochain passage. "
                 "Ne rien cocher = elles restent affichées.",
    },
    "sauver": {
        "label": "revue-sauver", "decision": "ajouter",
        "title": "À rattraper : activités « lb » déclaré mais rien dans le texte (non affichées)",
        "intro": "Ces activités **ne sont pas affichées**. L'organisateur a coché « lb » mais le texte ne le confirme pas. "
                 "**Cochez celles à ajouter** au site. Ne rien cocher = elles restent masquées.",
    },
}
ID_RE = re.compile(r"^- \[( |x|X)\] <!--id:([0-9a-f]{12})-->", re.M)


def gh(*args, check=True):
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=check)


def line(it):
    when = (it.get("start") or "")[:16].replace("T", " ")
    bits = [f"**{it['title']}**", when, it.get("venue") or "", it.get("reason") or ""]
    txt = f"- [ ] <!--id:{it['id']}--> " + " · ".join(b for b in bits if b)
    if it.get("url"):
        txt += f" · [fiche]({it['url']})"
    if it.get("snippet"):
        snippet = re.sub(r"\s+", " ", it["snippet"])
        txt += f"\n  > {snippet}…"
    return txt


def body_for(kind, items, ticked=()):
    cfg = LISTS[kind]
    shown = items[:MAX_ITEMS]
    rows = [line(it).replace("- [ ]", "- [x]", 1) if it["id"] in ticked else line(it) for it in shown]
    more = f"\n\n_{len(items) - MAX_ITEMS} autres à venir au prochain passage._" if len(items) > MAX_ITEMS else ""
    return f"@{OWNER}\n\n{cfg['intro']}\n\n" + "\n".join(rows) + more + "\n"


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
        if old_ids == new_ids:
            continue  # rien de changé : on ne touche pas à l'issue (les cases cochées en cours restent)
        ticked = {i for mark, i in ids_in(old) if mark.lower() == "x"}
        gh("issue", "edit", str(num), "--body", body_for(kind, items, ticked))
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
    ticked = [i for mark, i in ids_in(os.environ.get("ISSUE_BODY", "")) if mark.lower() == "x"]
    if not ticked:
        print("[revue] aucune case cochée")
        return
    path = DATA / "revue.json"
    try:
        revue = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        revue = {}
    key = LISTS[kind]["decision"]
    merged = sorted(set(revue.get(key, [])) | set(ticked))
    revue = {"retirer": revue.get("retirer", []), "ajouter": revue.get("ajouter", []), key: merged}
    path.write_text(json.dumps(revue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[revue] {len(ticked)} décision(s) enregistrée(s) ({key})")


if __name__ == "__main__":
    {"publish": publish, "apply": apply}[sys.argv[1]]()
