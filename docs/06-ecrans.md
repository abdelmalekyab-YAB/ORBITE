# 06 — Écrans (référence : `maquette/orbit-maquette.html`)

## Design system (à reprendre tel quel dans Tailwind)
- Fond `#070511`, surfaces `#100b20 / #171130 / #1f1840`, bordures `#2b2349`, texte `#f6f3ff`, secondaire `#c5bde0`, atténué `#8b83ab`
- Dégradé signature `linear-gradient(95deg,#e04bff,#a21caf 45%,#7c3aed)` ; violet `#a855f7` ; **néon** `#3dffb7` (= « à vous », validé) ; ambre `#ffc14d` (attente, devis) ; rose `#ff6b8a` (retard, refus) ; cyan `#3de1ff`
- Titres **Space Grotesk**, texte **Inter**. Boutons pilules : blanc = action principale, dégradé = créer/envoyer, néon = valider, rose = refuser
- Composants : `ball` (pastille « À vous / Chez Digitalia / En retard »), `track` (piste 6 étapes), `health` (Tout avance / À surveiller / En retard), `req` (ligne de demande avec piste), `act` (carte d'action « À vous de jouer »), `drawer` (fiche ticket en panneau latéral 720 px), `refus` (bloc rouge de refus avec pièces jointes), `kanban`, `hero` (accueil)
- Logo Digitalia : `maquette/logo_digitalia_icone.png` (icône), wordmark en texte « DIGITALIA » Space Grotesk letter-spacing .18em
- Responsive : sous 900 px, navigation en ligne défilante, grilles en une colonne, drawer plein écran

## Public
- **Accueil** : logo Digitalia, badge « Développé par Digitalia pour ses clients », titre, texte, CTA « Accéder à mon espace », visuel orbites animées (Digitalia au centre, clients en satellites), fond particules + ondes
- **Connexion** : e-mail, mot de passe, mot de passe oublié, pas encore d'accès ; erreurs explicites

## Espace client
- **Sélecteur de projet** en haut si plusieurs projets (« Tous mes projets (n) » / chaque projet)
- **Accueil** : hero (santé, « Bonjour X, n demandes attendent votre retour », compteurs à vous / chez Digitalia / livrées / en retard, anneau d'avancement de la version en cours) ; si multi-projets : une carte par projet ; « À vous de jouer » (tester, répondre, valider la proposition) ; « En cours chez Digitalia » ; « Ce qui a bougé »
- **Mes demandes** : filtres Toutes / À vous / Chez Digitalia / Livrées, recherche, lignes avec piste ; étiquette projet en mode « tous »
- **Feuille de route** : cartes versions (objectif, progression), contenu de la version sélectionnée, « pas encore planifié » ; un onglet par projet en mode « tous »
- **Nouvelle demande** (modale 3 étapes) : projet si plusieurs → type en tuiles (Quelque chose ne marche pas / Améliorer / Ajouter / Question) → titre, détails, impact (Bloquant / Gênant / Confort), pièces jointes (photo, vidéo, audio, message vocal, fichier) → récapitulatif
- **Fiche ticket (drawer)** : balle, piste, bannière contextuelle (tester / répondre / proposition / validation interne / livrée), proposition commerciale (accepter / refuser), description + pièces jointes, discussion (bulles, pièces jointes, composer avec photo/vidéo/vocal), informations, historique. **Refus** : bloc rouge en haut avec explication + pièces jointes, envoi bloqué sans motif

## Espace Digitalia
- **Cockpit** : cartes santé par projet, « À traiter maintenant » (En retard / À qualifier / Attente client / Devis en attente / À valider en interne / En test client), charge de l'équipe, activité
- **Triage** (pm/admin) : file gauche, panneau de qualification (type, priorité, responsable, version, date, estimation, facturation Inclus licence / Sur devis + proposition), actions Refuser / Précision / Analyse / Planifier ou Envoyer la proposition
- **Kanban** : colonnes issues du workflow, filtres projet / responsable / type / sous-tâches / recherche, drag & drop = transition (refus si non autorisée)
- **Projets** : cartes santé → projet : Demandes / Kanban / Versions / Interne / Finances (admin)
- **Équipe** : tickets en cours par membre, répartition
- **Finances** (admin) : cartes « rapporté depuis le début » par projet (barre dev / licence / évolutions / reste), sélecteur de mois, graphique et tableau mois × projet (+ coûts / marge si suivis), paramètres par projet (prix, échéances, licence, coûts), salaires & affectations, évolutions à chiffrer ; par projet : total en grand, 12 mois, échéances, devis
- **Accès** (admin) : équipe Digitalia (rôle, modifier, renvoyer invitation, mot de passe, désactiver, inviter), clients et utilisateurs (accès par projet, inviter, nouveau client), projets (responsable, archiver, nouveau projet avec prix et licence)
- **Réglages** (pm/admin) : workflow éditable (nom, étape client, balle, transitions, ordre, ajout, suppression, reset), ce que voit le client, notifications
