# 01 — Vision et fonctionnement d'Orbit

## En une phrase
Orbit est le point de contact unique entre Digitalia et chacun de ses clients **après la mise en production** d'un projet :
le client voit l'état réel de son projet et pousse ses demandes ; Digitalia pilote sans que le client ait à relancer.

## Le problème résolu
Les demandes arrivent par mail / WhatsApp / téléphone, se perdent, le client ne sait pas où ça en est, Digitalia
passe du temps en points d'avancement manuels. Jira fait ça pour des développeurs, pas pour un client final.

## Les acteurs
| Rôle | Organisation | Ce qu'il veut |
|---|---|---|
| **Utilisateur client** | Organisation cliente (WWS, RM Club…) | Savoir en 10 s où en est son projet, déposer une demande, tester, valider un devis |
| **Développeur** (`dev`) | Digitalia | Sa liste de travail, le kanban, le contexte de chaque ticket |
| **Chef de projet** (`pm`) | Digitalia | Trier, planifier, tenir le client informé, voir la charge |
| **Administrateur** (`admin`) | Digitalia | Tout + finances + gestion des accès, clients, projets |

Un client peut avoir **plusieurs projets** et **plusieurs utilisateurs**. Un utilisateur client n'a accès qu'aux projets
qu'on lui ouvre. Un client sans projet ouvert voit un écran vide « Aucun projet ouvert pour l'instant ».

## L'objet central : la demande (ticket)
Tout tourne autour du ticket. Deux notions font la valeur d'Orbit :

### 1. « La balle est chez qui »
À tout instant un ticket ouvert est **chez Digitalia** ou **chez le client**. C'est dérivé du statut via le workflow
(champ `ball` du statut). Il est affiché partout (liste, fiche, kanban, cockpit). Les statuts « chez le client » sont :
attente de précision, test client, devis à valider.

### 2. La visibilité
Les tâches internes (`is_internal=True` : refactos, sous-tâches techniques) n'existent pas pour le client. Il voit sa
demande et son étape, pas la mécanique. Le client voit en revanche l'étape **Validation interne** (test interne) pour
savoir que ça avance.

## Cycle de vie vu par le client (piste)
`Reçue → Planifiée → En développement → Validation interne → À tester → Livrée`
(+ « Proposition à valider » quand un devis est en attente, + « Clôturée » pour refusé/annulé).
Chaque statut interne est mappé sur une de ces étapes (voir `03-workflow.md`).

## Évolutions : licence ou devis
Quand une demande d'évolution / nouvelle fonctionnalité arrive, Digitalia décide en triage :
- **Inclus dans la licence** → planifiée normalement
- **Sur devis** → Digitalia rédige une **proposition commerciale** (montant HT, échéancier 1/2/3 parts, description, PDF),
  l'envoie ; le ticket passe « Devis à valider » (balle chez le client). Le client **accepte** (→ Planifiée, l'échéancier
  alimente les finances du projet) ou **refuse avec motif obligatoire** (→ Refusé). Le développement ne démarre qu'après accord.

## Finances (admin uniquement)
Par projet, deux recettes : le **prix du développement** (payé en une ou plusieurs échéances datées, chacune
« encaissée » ou non) et la **licence mensuelle** (montant + mois de début). Les devis acceptés s'ajoutent en recettes.
Les **coûts sont optionnels** : aucun / salaires par personne avec % d'affectation / montant mensuel par projet / jours × TJM
en coût unique. Vues : ce que chaque projet a rapporté depuis le début (dev / licence / évolutions / reste à encaisser /
devis en attente), mois par mois tous projets, détail par projet.

## Espaces
- **Accueil public** : page de présentation (développé par Digitalia pour ses clients) + connexion e-mail / mot de passe.
- **Espace client** : Accueil (santé, « À vous de jouer », en cours chez Digitalia, ce qui a bougé), Mes demandes, Feuille de route, Nouvelle demande (3 étapes sans jargon), fiche ticket en panneau latéral.
- **Espace Digitalia** : Cockpit, Triage (pm/admin), Kanban, Projets (Demandes / Kanban / Versions / Interne / Finances-admin), Équipe, Finances (admin), Accès (admin), Réglages (pm/admin).
