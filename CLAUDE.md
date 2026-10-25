# Orbit — instructions pour Claude Code

Orbit est le logiciel de suivi de projets entre **DIGITALIA** et ses clients : après la mise en production
d'un projet, le client suit l'état réel de son projet, dépose des demandes (bug, évolution, question, support),
teste ce qui est livré et valide les propositions commerciales. L'équipe Digitalia qualifie, planifie, développe,
teste en interne, livre, et pilote les finances.

## Sources de vérité
1. `docs/01-vision-et-fonctionnement.md` — ce que fait Orbit, pour qui, et LA règle centrale « la balle est chez qui »
2. `docs/02-modele-de-donnees.md` — modèles Django à créer, champs, contraintes
3. `docs/03-workflow.md` — statuts, transitions, mapping vers la piste client, configurabilité
4. `docs/04-regles-metier.md` — règles à ne pas négocier (visibilité, refus obligatoire, devis, finances)
5. `docs/05-api.md` — endpoints REST (DRF) et permissions par rôle
6. `docs/06-ecrans.md` — écrans et composants, alignés sur la maquette
7. `docs/07-plan-de-dev.md` — ordre de réalisation par sprints, critères d'acceptation
8. `docs/08-deploiement.md` — production (Caddy, Gunicorn, Celery, sauvegardes, supervision, RGPD)
9. `maquette/orbit-maquette.html` — maquette HTML interactive de référence (design + comportements). Ouvrir dans un navigateur ; comptes de démo dans le repli sous le formulaire de connexion, mot de passe `orbit`.

**En cas de doute entre la maquette et les docs, les docs priment pour le métier, la maquette prime pour le design.**

## Stack imposée
- Backend : **Python 3.12, Django 5, Django REST Framework, PostgreSQL**, Celery + Redis pour les tâches (e-mails, rappels), stockage fichiers S3-compatible (django-storages), authentification JWT (djangorestframework-simplejwt) ou session Django — choisir JWT.
- Frontend : SPA **React + Vite + TypeScript**, Tailwind CSS avec les tokens de design de la maquette (voir `docs/06-ecrans.md`). Pas de librairie UI lourde ; composants maison alignés sur la maquette.
- Tests : pytest + pytest-django côté back, Vitest + Testing Library côté front. Chaque règle métier de `docs/04-regles-metier.md` a au moins un test.
- Qualité : ruff + mypy (back), eslint + prettier (front). CI GitHub Actions.
- Docker Compose pour le dev local (db, redis, back, front, mailhog).

## Conventions
- Langue de l'interface : français. Code, noms de modèles, endpoints : anglais.
- Multi-tenant par `Organization` : un utilisateur client ne voit **jamais** les données d'une autre organisation ni les tickets `is_internal=True`. Cette règle est appliquée au niveau des querysets DRF, jamais seulement au niveau du front.
- Tout changement de statut passe par le service `workflow.transition(ticket, to_status, actor, comment=None, force=False)` qui vérifie les transitions autorisées et écrit l'historique. Aucune écriture directe de `ticket.status`.
- Les montants sont des `DecimalField(12,2)` en euros HT.
- Chaque endpoint de mutation écrit une ligne `TicketEvent` (historique) quand il concerne un ticket.

## Commandes attendues
- `make dev` : lance docker compose
- `make test` : back + front
- `make init EMAIL=... NAME="..."` : sur une base vide, crée l'organisation Digitalia et invite le premier administrateur.
  **Aucune donnée fictive dans l'application** : clients, projets, utilisateurs et tickets se saisissent dans Orbit.
  Le jeu de données de la maquette sert uniquement aux tests automatisés (`backend/tests_support/demo_data.py`).

## Ordre de travail
Suivre `docs/07-plan-de-dev.md` sprint par sprint. Ne pas commencer le front avant que l'API du sprint soit testée.
