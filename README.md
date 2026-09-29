# ◎ Orbit

Plateforme de gestion et de suivi de projets entre **Digitalia** et ses clients — inspirée de Jira, mais simplifiée côté client.

- **Le client** voit Orbit comme *son espace projet* : avancement, roadmap, demandes, discussions.
- **Digitalia** utilise Orbit comme *cockpit* de tous ses projets clients.

Hiérarchie : **Client → Projet → Roadmap (version / lot / sprint / jalon) → Ticket → Sous-tâches**

## Fonctionnalités (MVP)

| | Client | Digitalia |
|---|---|---|
| Arrivée après connexion | directement sur son projet | tableau de bord central |
| Projets visibles | uniquement ceux dont il est membre | tous |
| Créer une demande (évolution, bug, question, support, nouvelle fonctionnalité) | ✅ | ✅ (+ tâche interne) |
| Commenter, joindre fichiers / captures | ✅ | ✅ (+ notes internes) |
| Modifier statut, priorité, responsable, date cible, étape de roadmap, parent | — | ✅ |
| Tickets internes (invisibles du client) | — | ✅ |
| Filtres client / projet / type / priorité / statut / responsable / origine / visibilité / dates / retard | partiels | ✅ |
| Gérer la roadmap | lecture | ✅ |

- **Origine du ticket** calculée automatiquement : 🟣 Client, 🔵 Digitalia, ⚙️ Système.
- **Visibilité** : *Visible client* ou *Interne Digitalia*. Une demande client reste toujours visible par le client.
- Chaque ticket enregistre auteur, société, projet, date de création et un **historique complet** des modifications.
- Statuts : Nouveau, À analyser, À faire, En cours, En attente client, En test, Terminé, Refusé, Annulé.
  Quand le client répond à un ticket *En attente client*, il repasse automatiquement *À analyser*.
- Références par projet (`SCV-12`), recherche par référence.
- Pièces jointes servies via une vue qui vérifie les droits (jamais d'accès direct).
- Interface **FR / EN** (sélecteur dans la barre du haut).

## Démarrage

### Avec Docker

```bash
docker compose up -d
docker compose exec web python manage.py seed_demo      # données de démonstration
docker compose exec web python manage.py createsuperuser # optionnel
```

### En local (PostgreSQL requis)

```bash
pip install -r requirements.txt
# base « orbit », utilisateur/mot de passe « orbit » par défaut (voir variables ci-dessous)
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Ouvrir http://localhost:8000. Comptes de démo (mot de passe `orbit-demo`) :
`admin`, `yanis`, `sara` (Digitalia) — `wws`, `rmclub`, `bodytime` (clients).

### Variables d'environnement

| Variable | Défaut |
|---|---|
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | `orbit` |
| `POSTGRES_HOST` / `POSTGRES_PORT` | `localhost` / `5432` |
| `DJANGO_SECRET_KEY` | clé de dev — **à changer en production** |
| `DJANGO_DEBUG` | `true` |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` |
| `ORBIT_MEDIA_ROOT` | `./media` |

## Administration

Les sociétés, utilisateurs, projets (et leurs membres client) se gèrent dans `/admin/` :

1. Créer la société cliente, puis le compte client (rôle *Client*, société renseignée).
2. Créer le projet (clé courte, ex. `SCV`) et y ajouter le compte client dans *membres client*.
3. Les membres Digitalia ont le rôle *Équipe Digitalia* (cocher *statut équipe* pour l'accès à l'admin).

## Développement

```bash
python manage.py test
python manage.py makemessages -l fr -l en && python manage.py compilemessages  # après modification des textes
```

Structure : `core/` (sociétés, utilisateurs, projets, roadmap, tableaux de bord), `tickets/` (tickets, commentaires, pièces jointes, historique), `templates/`, `static/`, `locale/`.
