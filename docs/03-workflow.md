# 03 — Workflow

## Workflow par défaut (migration de données)
| key | label interne | client_label | ball | closed | next (transitions autorisées) |
|---|---|---|---|---|---|
| nouveau | Nouveau | Reçue | digitalia | | analyser, faire, devis, refuse |
| analyser | À analyser | Reçue | digitalia | | faire, devis, attente, refuse |
| devis | Devis à valider | Proposition à valider | **client** | | faire, refuse, analyser |
| faire | À faire | Planifiée | digitalia | | cours, annule |
| cours | En cours | En développement | digitalia | | testint, attente, faire |
| testint | Test interne | Validation interne | digitalia | | test, cours |
| attente | En attente client | En développement | **client** | | cours, annule |
| test | Test client | À tester | **client** | | termine, cours |
| termine | Terminé | Livrée | none | oui (terminal_ok) | cours (rouvrir) |
| refuse | Refusé | Clôturée | none | oui | analyser |
| annule | Annulé | Clôturée | none | oui | faire |

`nouveau`, `termine`, `refuse`, `annule` sont `is_system=True` (non supprimables).

## Piste client
`STEPS` = liste ordonnée des `client_label` distincts des statuts non clôturés, dans l'ordre du workflow, + « Livrée ».
L'étape d'un ticket = index de `status.client_label` dans STEPS. Un statut clôturé non-OK affiche « Clôturée ».

## Service de transition (obligatoire)
```python
workflow.transition(ticket, to_status_key, actor, *, comment=None, attachments=None, force=False) -> Ticket
```
- vérifie `to in ticket.status.next` sauf `force=True` (réservé au triage et aux actions système : acceptation de devis, refus)
- écrit `TicketEvent(kind='status', from, to)`
- si le statut cible est clôturé : `closed_at=now`
- déclenche les notifications (voir 04)
- lève `TransitionNotAllowed` sinon (→ HTTP 409)

## Configurabilité (Réglages → Workflow, rôle pm/admin)
- Renommer label / client_label, changer `ball`, réordonner, ajouter un statut, cocher/décocher les transitions
- Supprimer un statut interdit si des tickets l'utilisent (HTTP 409 avec le nombre) ou s'il est `is_system`
- « Revenir au workflow par défaut » recharge la table par défaut
- Par projet : au premier « personnaliser », copie du workflow global vers le projet ; sinon le projet utilise le global
- Le kanban construit ses colonnes depuis le workflow : une colonne par statut non clôturé-négatif, en regroupant tous les
  statuts `ball=client` dans une colonne « Chez le client »

## Actions rapides (raccourcis de transition, tous passent par `transition`)
| Qui | Action | Transition |
|---|---|---|
| Digitalia | Passer en test interne | cours → testint |
| Digitalia | Validé, envoyer au client | testint → test |
| Digitalia | Retour en dev | testint → cours |
| Digitalia | Demander une précision | cours/analyser → attente |
| Digitalia | Démarrer | faire → cours |
| Digitalia | Relancer | pas de transition, commentaire + notification |
| Client | C'est bon (test OK) | test → termine |
| Client | Pas OK (**motif obligatoire**) | test → cours |
| Client | J'ai répondu / commentaire en attente | attente → cours (automatique quand le client commente) |
| Client | Rouvrir (**motif obligatoire**) | termine → cours |
| Client | Accepter la proposition | devis → faire (force) |
| Client | Refuser la proposition (**motif obligatoire**) | devis → refuse (force) |
