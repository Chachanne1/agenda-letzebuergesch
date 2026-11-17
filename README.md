# Agenda Lëtzebuergesch

Rassemble les activités en luxembourgeois au Luxembourg.
Sammel d'Aktivitéiten op Lëtzebuergesch zu Lëtzebuerg zesummen.

Site : https://chachanne1.github.io/agenda-letzebuergesch

## Comment ça marche

```
sources.json → scrapers/run.py (chaque jour, GitHub Actions)
            → data/events.json (validés) + data/pending.json (à valider)
            → scrapers/build.py → _site/ → GitHub Pages
```

- Aucune dépendance : Python 3.11 (bibliothèque standard) côté collecte, HTML/JS simple côté site.
- La collecte tourne chaque jour via `.github/workflows/update.yml` (aussi lançable à la main : onglet *Actions* → *Run workflow*).

## Ajouter une source

Éditer `sources.json` :

```json
{ "name": "Nom du lieu", "type": "ical", "url": "https://.../agenda.ics", "lb_only": false, "enabled": true }
```

- `type: "ical"` : flux .ics. `type: "jsonld"` : page(s) web avec des blocs schema.org/Event (`"urls": [...]` pour plusieurs pages). `type: "wpjson"` : API REST WordPress avec champs `meta.event_*` (cas de uni.lu).
- Pour savoir quel format un site offre : `python scrapers/probe.py https://site.lu/agenda` (sans argument, teste toutes les URLs de `sources.json`).
- `lb_only: true` si tous les événements de la source sont en luxembourgeois.

## Détection de la langue

Chaque événement reçoit un statut :
- **confirmé** : langue indiquée par la source, mention explicite (« op Lëtzebuergesch », « en luxembourgeois »…) ou source `lb_only` → publié directement ;
- **probable** : texte qui semble luxembourgeois, ou simple mention de la langue → placé dans `data/pending.json` ;
- sans aucun indice : écarté.

## Valider les événements « probables »

Dans `data/pending.json`, mettre `"decision": "approve"` ou `"decision": "reject"` (éditable directement sur GitHub). Au prochain passage du workflow, l'événement est publié ou définitivement écarté.

## Tester en local

```
python scrapers/run.py
python scrapers/build.py
cd _site
python -m http.server 8000      # puis ouvrir http://localhost:8000
```
