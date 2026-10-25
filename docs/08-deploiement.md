# 08 — Déploiement et exploitation

## Architecture de production (`docker-compose.prod.yml`)
| Service | Rôle |
|---|---|
| `web` | **Caddy** : HTTPS automatique (Let's Encrypt), sert le front React compilé, relaie `/api` et `/admin` vers le backend, sert `/static` |
| `backend` | Django + **Gunicorn** (3 workers). Au démarrage : `migrate` puis `collectstatic` |
| `worker` | **Celery** worker + beat : e-mails transactionnels, rappel client (9 h), digest quotidien (8 h) |
| `db` | PostgreSQL 16 (volume `pgdata`) |
| `redis` | broker Celery |
| `backup` | `pg_dump` compressé chaque jour dans `./backups`, rétention `BACKUP_RETENTION_DAYS` (14 j par défaut) |

Pièces jointes et PDF de propositions : stockage **S3-compatible** dès que `AWS_STORAGE_BUCKET_NAME` est défini
(URL signées, jamais publiques). Sans bucket, les fichiers restent sur le disque du conteneur : réservé au développement.

## Mise en production
1. Serveur Linux avec Docker, DNS du domaine pointant vers lui, ports 80 et 443 ouverts.
2. `cp .env.prod.example .env.prod` puis renseigner : domaine, `DJANGO_SECRET_KEY`, mot de passe PostgreSQL, SMTP, bucket S3.
3. `make prod` (ou `docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build`).
4. Créer le premier administrateur (il reçoit un lien pour définir son mot de passe) :
   `docker compose -f docker-compose.prod.yml --env-file .env.prod exec backend python manage.py init_orbit --email ... --name "Prénom Nom"`
   Les autres comptes, clients et projets se créent depuis l'écran **Accès**. L'application ne contient aucune donnée de démonstration.

## Supervision
- `GET /api/v1/health` : `200 {"status": "ok", "database": "ok", "broker": "ok"}`, `503` si la base ou Redis est indisponible
  (utilisé par le healthcheck Docker du backend ; à brancher sur un moniteur externe type UptimeRobot).
- Logs : sortie standard de chaque conteneur (`docker compose ... logs -f backend worker`), niveau `LOG_LEVEL`.
- Erreurs applicatives : Sentry si `SENTRY_DSN` est défini (sans données personnelles).

## Sauvegardes et restauration
- Fichiers : `./backups/orbit-AAAAMMJJ-HHMM.sql.gz` (à copier hors du serveur : rsync / stockage objet).
- Restaurer :
  `gunzip -c backups/orbit-XXXX.sql.gz | docker compose -f docker-compose.prod.yml --env-file .env.prod exec -T db psql -U orbit orbit`

## Sécurité
- `DJANGO_DEBUG=0` impose un `DJANGO_SECRET_KEY` (le démarrage échoue sinon).
- Cookies sécurisés, HSTS, `nosniff`, `X-Frame-Options: DENY` (Caddy + Django).
- JWT : accès 8 h, rafraîchissement 30 j. Liens d'invitation / réinitialisation : 7 jours, usage unique.

## RGPD
- **Suppression d'un compte** (écran Accès → Supprimer, ou `DELETE /api/v1/users/{id}`) : e-mail, nom et mot de passe effacés,
  accès et notifications supprimés. L'historique des demandes est conservé, attribué à « Utilisateur supprimé ».
- Exports CSV : les clients n'exportent que leurs demandes visibles (jamais les tâches internes).

## Vérifié
La pile a été démarrée localement avec `DOMAIN=localhost` : santé API OK, SPA et routes internes servies, redirection
HTTP → HTTPS, en-têtes de sécurité présents, fichiers statiques de l'admin servis, première sauvegarde écrite.
