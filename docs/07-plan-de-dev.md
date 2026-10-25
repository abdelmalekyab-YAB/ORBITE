# 07 — Plan de développement

Chaque sprint : API testée (pytest) **puis** front. Critère de fin = démo jouable avec `make seed`.

## Sprint 0 — Socle (1 sem.)
- Repo, Docker Compose (postgres, redis, back, front, mailhog), CI, ruff/mypy/eslint, `make dev/test/seed`
- Modèles Organization, User, Project, ProjectAccess, Milestone, WorkflowStatus + migration du workflow par défaut
- Auth JWT, invitation, reset mot de passe, `/me`
- Front : accueil public, connexion, shell (topbar, navigation par rôle), design tokens
- ✅ Julie se connecte et voit un shell vide avec ses 2 projets

## Sprint 1 — Tickets et workflow (2 sem.)
- Ticket, Comment, Attachment (S3), TicketEvent, service `transition`, numérotation
- API tickets / comments / events / transition / board
- Front client : Accueil, Mes demandes, Nouvelle demande (3 étapes + pièces jointes), drawer complet, refus obligatoire
- Front Digitalia : Cockpit, Kanban (drag & drop), Projets → Demandes / Kanban / Interne, Équipe
- ✅ Règles 6-12 testées ; un bug déposé par Julie passe cours → testint → test → « Pas OK » avec vocal → cours → test → livré

## Sprint 2 — Triage, devis, roadmap (1,5 sem.)
- Quote, QuoteInstallment, API triage / quote
- Front : Triage, proposition commerciale côté Digitalia, acceptation / refus côté client, Feuille de route (versions)
- ✅ Règles 13-18 ; une évolution sur devis est proposée, acceptée, planifiée

## Sprint 3 — Finances (1,5 sem.)
- ProjectFinance, DevInstallment, StaffCost/Allocation, FinanceSettings, service finance (revenue/cost/summary) testé sur des cas datés
- API finance, front Finances + onglet Finances du projet
- ✅ Règles 19-22 ; les chiffres de la maquette sont reproduits par le seed

## Sprint 4 — Accès, réglages, notifications (1 sem.)
- API organizations / users / project-access / workflow PUT / settings
- Front Accès (équipe, clients, projets, création), Réglages (workflow éditable, notifications)
- Celery : e-mails transactionnels (mailhog en dev), rappel 3 jours, digest quotidien
- ✅ Règles 1-5, 24-26 ; l'admin crée un client, un projet, invite un utilisateur qui se connecte

## Sprint 5 — Finitions et mise en production
- Responsive, accessibilité clavier, états vides, performances (index sur project/status/assignee/due_on)
- Export CSV des tickets et des finances ; PDF de proposition généré si non joint
- Déploiement (Docker, reverse proxy, HTTPS, sauvegardes Postgres, stockage S3), monitoring, RGPD (suppression compte)

## Hors périmètre V1 (noté pour la V2)
Intégrations GitHub/GitLab/Slack, API publique, temps passé par ticket, SLA contractuels, facturation automatique (factures PDF, relances), application mobile.
