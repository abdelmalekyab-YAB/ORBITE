# Démo en ligne (GitHub Pages)

Orbit complet (API Django + interface React) qui tourne **dans le navigateur du visiteur** grâce à Pyodide :
aucun serveur, données de démonstration propres à chaque appareil, boîte mail de démo, bouton de remise à zéro.
Ce n'est pas la production (voir `docs/08-deploiement.md`) : rien n'est partagé entre visiteurs.

- `settings.py` / `urls.py` : réglages Django propres à la démo (SQLite, e-mails en mémoire, Celery synchrone).
- `web/` : `bridge.js` (branché devant l'app React, relaie les appels `/api` vers Django), `worker.js` (Pyodide),
  `boot.py` (répond aux requêtes).
- `build.py` : construit le site dans un dossier (front compilé avec `--base`, Django, données de démo).

Le jeu de données vient de `backend/tests_support/demo_data.py` ; il n'est jamais chargé en production.
