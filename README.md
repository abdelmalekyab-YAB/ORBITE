# Orbit

Suivi de projets entre Digitalia et ses clients. Voir `CLAUDE.md` et `docs/`.

## Démarrer (développement)
```bash
cp .env.example .env
make dev        # back http://localhost:8000, front http://localhost:5173, mailhog http://localhost:8025
make migrate
make init EMAIL=prenom@digitalia-ltd.com NAME="Prénom Nom"   # premier admin : lien d'invitation affiché + e-mail
make test       # pytest (back) + vitest (front)
make lint       # ruff + mypy, eslint + prettier + tsc
```
Sous Windows sans `make` : `.\make.ps1 dev` (mêmes cibles ; `.\make.ps1 init -Email ... -Name "..."`).
Docker Desktop doit être démarré.

La base ne contient **aucune donnée fictive** : après `init`, l'administrateur crée les clients, projets et
utilisateurs dans l'écran **Accès** ; les clients déposent leurs demandes ; tout est enregistré en base.
En développement, les e-mails (invitations, notifications) arrivent dans MailHog (http://localhost:8025).

## Production
Voir `docs/08-deploiement.md` : `cp .env.prod.example .env.prod`, puis `make prod`.

## Qualité
CI GitHub Actions (`.github/workflows/ci.yml`) : ruff, mypy, pytest (PostgreSQL + Redis), eslint, prettier, tsc,
vitest, build, images Docker de production.
