# 04 — Règles métier (chacune a un test)

## Accès et visibilité
1. Un utilisateur client ne voit que les tickets de ses projets (`ProjectAccess`) **et** `is_internal=False`. Appliqué dans les querysets DRF.
2. Un client ne voit ni les sous-tâches internes, ni l'onglet Interne, ni les champs `assignee` en édition, ni les finances.
3. Rôles Digitalia : `dev` = Cockpit, Kanban, Projets, Équipe ; `pm` = + Triage, Réglages ; `admin` = + Finances, Accès (gestion utilisateurs/clients/projets). Les permissions sont vérifiées côté API.
4. Un compte désactivé ne peut pas se connecter (message explicite). Un compte invité (`invited_at`, pas `activated_at`) se connecte via le lien d'invitation et définit son mot de passe ; `activated_at` est posé à la première connexion.
5. Un client sans `ProjectAccess` actif voit un écran vide, pas une erreur.

## Tickets
6. Numérotation `{PROJECT_KEY}-{n}` séquentielle par projet, jamais réutilisée.
7. Création par un client : `origin=client`, `status=nouveau`, `is_internal=False`, priorité choisie via Confort/Gênant/Bloquant → normal/high/critical. Pièces jointes possibles à la création (photo, vidéo, audio, fichier).
8. Création par Digitalia : statut initial `faire` (ou `nouveau` si l'auteur le demande), visibilité au choix, type « Tâche interne » ⇒ `is_internal=True`.
9. Toute modification de statut passe par `workflow.transition` (voir 03). Tentative de transition non autorisée ⇒ 409.
10. **Refus obligatoire** : « Pas OK », « Rouvrir », « Refuser la proposition » exigent un commentaire (`kind` dédié) contenant soit ≥ 10 caractères de texte, soit au moins une pièce jointe audio ou vidéo. Sinon 400 avec message. Le refus apparaît dans la discussion avec ses pièces jointes et dans l'historique.
11. Quand un client commente un ticket en `attente`, il repasse automatiquement en `cours` (la balle revient chez Digitalia).
12. Un ticket dont la date cible est dépassée et non clôturé est « en retard » (calcul, pas un statut).

## Triage (pm/admin)
13. Le triage liste les tickets `nouveau` et `analyser`. Décisions : Planifier (→ faire), Garder en analyse, Demander une précision (→ attente), Refuser (→ refuse), Envoyer la proposition (→ devis). Chaque décision peut porter type, priorité, responsable, version, date cible, estimation, message au client (commentaire).
14. Pour `evolution`/`feature`, `billing` doit être `licence` ou `quote` avant planification. `quote` exige une proposition (montant > 0).

## Devis
15. Envoi : `Quote.status=sent`, `sent_at`, ticket → `devis` (force), événement + notification client.
16. Acceptation par un utilisateur client ayant accès : `accepted`, `decided_at/by`, génération des `QuoteInstallment` (100 / 50-50 / 30-40-30 ; première échéance au jour de l'acceptation, suivantes à +45 j chacune, modifiables par l'admin), ticket → `faire`. Les échéances entrent dans les recettes du projet.
17. Refus : motif obligatoire (règle 10), `refused`, ticket → `refuse`.
18. Digitalia peut modifier une proposition `sent` (retour en `draft` puis renvoi) et relancer.

## Finances (admin)
19. `revenue(project, month)` et `cost(project, month)` selon `02-modele-de-donnees.md`. Les coûts sont **optionnels** ; sans coût, aucune marge n'est affichée (on montre « encaissé depuis le début » à la place).
20. La licence est comptée chaque mois de `licence_start` jusqu'à `licence_end` (ou aujourd'hui/projection).
21. Somme des `StaffAllocation.percent` d'une personne : avertissement (pas blocage) si > 100.
22. Les estimations en jours servent d'aide au chiffrage (`estimate_days × default_tjm`) ; elles n'entrent jamais dans les recettes.

## Santé d'un projet (calcul)
23. `late` si ≥ 1 ticket en retard ; sinon `watch` si ≥ 2 `nouveau` ou ≥ 1 `attente` ; sinon `ok`. Chaque valeur a une phrase de raison.

## Notifications (Celery)
24. Client : reçue & qualifiée ; planifiée dans une version (date) ; précision demandée ; prête à tester ; proposition envoyée ; livrée ; rappel après 3 jours sans réponse quand la balle est chez lui (configurable).
25. Digitalia : nouvelle demande (responsable du projet + pm), le client a répondu / testé / décidé sur un devis, digest quotidien des nouvelles demandes.
26. Aucune notification pour un événement sur un ticket `is_internal`.
