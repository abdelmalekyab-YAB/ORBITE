# 09 — Module Facturation (`apps.billing`)

Reprise dans Orbit de l'outil de pilotage financier de Digitalia. Réservé à l'administration
(`is_orbit_admin`) : tout autre compte reçoit 403, y compris les chefs de projet.

## Où le trouver
- API : `/api/v1/billing/…` (tableau de bord, saisie du mois, à venir, récap, profils, factures,
  occurrences fixes, dépenses, export comptable `.xlsx`/`.zip`, synthèse PDF, synchro Zoho).
- Écran : onglet **Finances** → sous-onglet **Facturation**. L'ancien écran
  « Rentabilité par projet » (`apps.finance`) reste disponible à côté.

## Rattachement à Orbit
- Un client du module = une `Organization` de type client ; un projet = un `projects.Project`.
- Un projet devient facturable quand on lui crée un profil de facturation
  (Clients & projets → projets Orbit sans profil).

## Reprise de l'historique (serveur de production uniquement)
Les données réelles ne sont **jamais** dans le dépôt (il est public) ni dans la démo GitHub Pages.

```bash
# fichiers copiés à la main sur le serveur, hors dépôt
docker compose -f docker-compose.prod.yml exec back python manage.py import_legacy /srv/finance-data/export_plateforme.json
docker compose -f docker-compose.prod.yml exec back python manage.py check_reference /srv/finance-data/reference_totals.json
```
L'import est idempotent : il rattache les clients existants par nom et crée ceux qui manquent.
`check_reference` doit répondre « Tous les totaux correspondent ».

## Zoho Books
Lecture seule absolue : le client ne contient aucune méthode d'écriture (testé).
Renseigner `ZOHO_ORGANIZATION_ID`, `ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET`, `ZOHO_REFRESH_TOKEN`
dans `.env.prod` (scopes `*.READ`).

## Tests
- `apps/billing/tests/test_orbit_integration.py` : accès admin seul, règles de calcul sur données fictives, import.
- `apps/billing/tests/test_reference.py` : test d'or sur les vraies données, exécuté seulement si
  `ORBIT_FINANCE_DATA` pointe vers le dossier d'export (jamais en CI).

## Points à trancher
Les anomalies relevées dans l'export (factures non planifiées, brouillon Zoho, rattachement client)
sont suivies hors dépôt. Reste ouvert ici : doublon fonctionnel avec `apps.finance`
(garder les deux vues ou fusionner).
