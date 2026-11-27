// Réglages du formulaire « Aktivitéit virschloen ». Tant que `endpoint` est vide, le bouton reste caché.
// À remplir après l'installation (voir SETUP-FORMULAIRE.md). Ces deux valeurs sont publiques, ce n'est pas un secret.
window.AGENDA_FORM = {
  endpoint: "",          // ex. "https://agenda-propositions.TON-COMPTE.workers.dev"
  turnstileSiteKey: ""   // clé de SITE Turnstile (la clé secrète, elle, reste dans Cloudflare)
};
