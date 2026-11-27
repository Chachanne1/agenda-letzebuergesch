"""Collecte quotidienne : lit sources.json, collecte, détecte la langue, fusionne.

Fichiers produits/mis à jour :
  data/events.json    événements validés (affichés sur le site)
  data/pending.json   événements "probables" à valider (decision: approve / reject)
  data/rejected.json  identifiants rejetés (ne reviennent plus)
  data/status.json    état de chaque source (pour repérer les scrapers cassés)
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import echo_api
import echo_html
import ical_source
import jsonld_source
import wpjson_source
from common import classify_echo, detect_lb, today_iso

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SCRAPERS = {"ical": ical_source, "jsonld": jsonld_source, "wpjson": wpjson_source, "echo_html": echo_html, "echo_api": echo_api}


def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def is_upcoming(ev, today):
    ref = (ev.get("end") or ev.get("start") or "")[:10]
    return ref >= today


def revue_item(ev, reason):
    keys = ("id", "title", "start", "end", "venue", "url")
    return {**{k: ev.get(k, "") for k in keys}, "reason": reason, "snippet": (ev.get("description") or "")[:250]}


def main():
    today = today_iso()
    sources = load(ROOT / "sources.json", [])
    events = {e["id"]: e for e in load(DATA / "events.json", [])}
    pending = {e["id"]: e for e in load(DATA / "pending.json", [])}
    rejected = set(load(DATA / "rejected.json", []))
    # décisions prises dans les issues de revue (voir revue.py) : {"retirer": [ids], "ajouter": [ids]}
    revue = load(DATA / "revue.json", {})
    retirer, ajouter = set(revue.get("retirer", [])), set(revue.get("ajouter", []))
    ecarter = set(revue.get("ecarter", []))  # « écarter définitivement » (cases des issues de revue)
    queue = load(DATA / "revue_queue.json", {"verifier": [], "sauver": []})
    status = []

    # 1) Appliquer les décisions prises à la main dans pending.json
    for pid, ev in list(pending.items()):
        decision = ev.get("decision")
        if decision == "approve":
            ev = {k: v for k, v in ev.items() if k != "decision"}
            ev["status"] = "confirmé"
            ev["reason"] = "validé manuellement"
            events[pid] = ev
            del pending[pid]
        elif decision == "reject":
            rejected.add(pid)
            del pending[pid]

    # 2) Collecter
    for src in sources:
        if not src.get("enabled", True):
            continue
        entry = {"name": src["name"], "ok": False, "found": 0, "kept": 0, "error": ""}
        try:
            found = SCRAPERS[src["type"]].scrape(src)
            entry["found"] = len(found)
            if src["type"] == "echo_api":
                queue = {"verifier": [], "sauver": []}
                found_ids = set()
                # l'API renvoie tout à chaque fois : on repart de ses données fraîches (annulations, titres corrigés…)
                for store in (events, pending):
                    for k in [k for k, v in store.items() if v.get("source") == src["name"]]:
                        del store[k]
            for ev in found:
                if not is_upcoming(ev, today) or ev["id"] in rejected:
                    continue
                if src["type"] == "echo_api":
                    found_ids.add(ev["id"])
                    voie, reason = classify_echo(ev["title"], ev["description"], ev.pop("_langs", []))
                    ev.pop("_lang", None)
                    if voie is None or ev["id"] in retirer or ev["id"] in ecarter:
                        continue
                    if voie == "sauver":
                        if ev["id"] not in ajouter:
                            if not any(q["id"] == ev["id"] for q in queue["sauver"]):
                                queue["sauver"].append(revue_item(ev, reason))
                            continue
                        voie, reason = "confirmé", "rattrapé manuellement"
                    ev["status"] = "confirmé" if voie == "confirmé" else "probable"
                    ev["reason"] = reason
                    if voie == "verifier" and not any(q["id"] == ev["id"] for q in queue["verifier"]):
                        queue["verifier"].append(revue_item(ev, reason))
                    entry["kept"] += 1
                    events[ev["id"]] = ev
                    continue
                lang = ev.pop("_lang", "")
                st, reason = detect_lb(ev["title"], ev["description"], lang, src.get("lb_only", False))
                if st is None:
                    continue
                ev["status"], ev["reason"] = st, reason
                entry["kept"] += 1
                if ev["id"] in events:
                    # on garde la version validée mais on rafraîchit les infos pratiques
                    events[ev["id"]].update({k: ev[k] for k in ("start", "end", "venue", "address", "url")})
                elif st == "confirmé":
                    events[ev["id"]] = ev
                    pending.pop(ev["id"], None)
                elif ev["id"] not in pending:
                    ev["decision"] = None
                    pending[ev["id"]] = ev
            if src["type"] == "echo_api":
                retirer &= found_ids  # on oublie les décisions sur des événements qui ne sont plus dans l'API
                ajouter &= found_ids
                ecarter &= found_ids
            entry["ok"] = True
        except Exception as exc:  # une source cassée ne doit pas bloquer les autres
            entry["error"] = f"{type(exc).__name__}: {exc}"
        status.append(entry)

    # 3) Supprimer les événements passés, trier, enregistrer
    events = {k: v for k, v in events.items() if is_upcoming(v, today)}
    pending = {k: v for k, v in pending.items() if is_upcoming(v, today)}
    save(DATA / "events.json", sorted(events.values(), key=lambda e: e["start"]))
    save(DATA / "pending.json", sorted(pending.values(), key=lambda e: e["start"]))
    save(DATA / "rejected.json", sorted(rejected))
    save(DATA / "revue.json", {"retirer": sorted(retirer), "ajouter": sorted(ajouter), "ecarter": sorted(ecarter)})
    save(DATA / "revue_queue.json", queue)
    save(DATA / "status.json", {
        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sources": status,
    })

    broken = [s for s in status if not s["ok"] or s["found"] == 0]
    for s in status:
        flag = "OK " if s in status and s not in broken else "!! "
        print(f"{flag}{s['name']}: {s['found']} trouvés, {s['kept']} retenus {s['error']}")
    print(f"Total : {len(events)} événements validés, {len(pending)} à valider.")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
