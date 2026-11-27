# Formulaire « Aktivitéit virschloen » : mise en route

Chaîne complète : **formulaire du site → Worker Cloudflare (gratuit) → issue GitHub « proposition » → tu ajoutes l'étiquette `valider` → l'événement est revalidé puis publié.**
Rien n'est publié sans ton clic. Tant que `site/config.js` est vide, le bouton reste invisible : tu peux mettre le code en ligne avant d'avoir tout installé.

## 1. Étiquettes du dépôt (2 min)
GitHub → dépôt → **Issues → Labels → New label**, crée : `proposition`, `valider`, `refuser`.

## 2. Jeton GitHub limité à ce dépôt (3 min)
GitHub → ton avatar → **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**
- Repository access : **Only select repositories** → `agenda-letzebuergesch`
- Permissions → Repository permissions → **Issues : Read and write** (rien d'autre)
- Expiration : 1 an maximum (note la date : à renouveler)
- Copie le jeton (`github_pat_…`) **sans le coller dans le chat** ni dans un fichier du dépôt.

## 3. Turnstile, l'anti-robots gratuit de Cloudflare (3 min)
Cloudflare (crée un compte gratuit si besoin) → **Turnstile → Add widget**
- Hostname : `chachanne1.github.io`
- Mode : **Managed**
- Tu obtiens une **clé de site** (publique) et une **clé secrète** (à garder).

## 4. Le Worker (5 min)
Cloudflare → **Workers & Pages → Create → Create Worker** → nom `agenda-propositions` → Deploy → **Edit code** → efface tout, colle le contenu de `cloudflare/worker.js` → **Deploy**.
Puis **Settings → Variables and Secrets** :

| Nom | Type | Valeur |
|---|---|---|
| `GITHUB_TOKEN` | Secret | le jeton de l'étape 2 |
| `TURNSTILE_SECRET` | Secret | la clé secrète de l'étape 3 |
| `GITHUB_REPO` | Texte | `Chachanne1/agenda-letzebuergesch` |
| `ALLOWED_ORIGIN` | Texte | `https://chachanne1.github.io` (sans `/` final) |

Note l'adresse du Worker : `https://agenda-propositions.<ton-compte>.workers.dev`.

## 5. Brancher le site
Dans `site/config.js`, renseigne :
```js
endpoint: "https://agenda-propositions.<ton-compte>.workers.dev",
turnstileSiteKey: "<clé de site de l'étape 3>"
```
puis `git add . && git commit -m "Formulaire activé" && git pull --rebase && git push`. Le bouton « + Aktivitéit virschloen » apparaît après le déploiement.

## 6. Utilisation au quotidien
1. Une proposition arrive : issue **« Proposition : … »** (tu reçois l'e-mail GitHub habituel).
2. Regarde le contenu **sans cliquer sur le lien** : lis le domaine, vérifie-le (ou ouvre-le depuis un navigateur sans compte connecté).
3. Ajoute l'étiquette **`valider`** → Actions revalide, ajoute à `data/events.json`, ferme l'issue et relance la construction du site. Ou **`refuser`** → l'issue est fermée.

## Ce qui protège le site
- **Rien d'automatique** : publication uniquement après ton étiquette.
- **Le lien n'est jamais ouvert** par un programme ; il est seulement affiché sur le site avec `rel="noopener noreferrer nofollow ugc"`.
- **Liens filtrés** : `https` obligatoire ; refus de `javascript:`, `data:`, adresses IP, `localhost`, identifiants dans l'URL (`user:pw@`), noms en punycode (faux sites avec lettres piégées), raccourcisseurs (bit.ly…), ports inhabituels ; paramètres de suivi (`utm_*`, `fbclid`…) retirés ; pas de lien dans le titre/lieu, 2 liens maximum dans la description.
- **Texte** : longueurs limitées, `< >` refusés, caractères invisibles et de contrôle retirés ; le site échappe tout (`esc()`).
- **Dans l'issue** : tout est enfermé dans un bloc de code (pas de rendu Markdown, pas de `@mentions`) ; le titre est nettoyé.
- **Dans Actions** : le texte de l'issue n'est jamais collé dans une commande shell ; un script Python le relit et **revalide tout** (une issue ouverte à la main par un inconnu passerait par la même validation).
- **Anti-spam** : Turnstile + champ-piège invisible + origine imposée (`ALLOWED_ORIGIN`) + corps limité à 8 Ko.
- **Vie privée** : le formulaire ne demande aucun e-mail (les issues sont publiques).
- **Jeton** : limité à ce dépôt et à « Issues » ; si tu le crois compromis, révoque-le dans GitHub et mets-en un autre dans le Worker.

## Tests (optionnel)
`python tests/test_propositions.py` et `node --test tests/worker.test.mjs` : les deux utilisent les mêmes 33 cas (`tests/validation_cases.json`) pour garantir que le Worker et le script Python appliquent les mêmes règles.

## Limites connues
- Offre gratuite Cloudflare : 100 000 requêtes/jour pour le Worker ; Turnstile gratuit.
- Les textes du formulaire en luxembourgeois sont de moi : relis-les.
- Tant que le site tourne sur `github.io`, l'origine autorisée est `https://chachanne1.github.io` ; si tu achètes un domaine, change `ALLOWED_ORIGIN` et le hostname Turnstile.
