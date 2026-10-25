# 05 — API REST (DRF)

Préfixe `/api/v1/`. Auth JWT (`/auth/login`, `/auth/refresh`, `/auth/logout`). Réponses JSON, pagination cursor,
erreurs `{ "detail": "...", "code": "..." }`. Toutes les listes sont filtrées par le scope de l'utilisateur (règles 1-3).

## Auth & compte
| Méthode | Route | Rôle | Note |
|---|---|---|---|
| POST | /auth/login | tous | email + password → tokens + `me` |
| POST | /auth/password/forgot, /auth/password/reset | tous | e-mail de réinitialisation |
| POST | /auth/invite/accept | tous | token d'invitation → définit le mot de passe, pose `activated_at` |
| GET | /me | tous | profil, organisation, job, projets accessibles |

## Référentiels
| GET | /projects | tous | scope ; `?include_archived=1` (Digitalia) |
| GET/PATCH | /projects/{key} | tous / pm,admin |
| POST | /projects | admin | crée `Project` + `ProjectFinance` (dev_price, licence) ; ouvre l'accès aux utilisateurs du client |
| POST | /projects/{key}/archive, /unarchive | admin |
| GET/POST/PATCH/DELETE | /projects/{key}/milestones | Digitalia |
| GET | /workflow[?project=KEY] | tous | statuts + transitions + STEPS + `customized` |
| PUT | /workflow[?project=KEY] | pm,admin | remplace la config ; 409 si suppression d'un statut utilisé |
| POST | /workflow/reset | pm,admin |

## Tickets
| GET | /tickets | tous | filtres : project, status, ball (`client`/`digitalia`), type, priority, assignee (`me`/id/`none`), origin, milestone, late=1, closed=1, q, parent ; tri |
| POST | /tickets | tous | multipart (pièces jointes) ; règles 7-8 |
| GET/PATCH | /tickets/{id} | tous / champs restreints côté client (rien) ; Digitalia : title, description, type, priority, assignee, milestone, due_on, is_internal, billing, estimate_days |
| POST | /tickets/{id}/transition | selon action | `{to, comment?, attachments?}` → service transition (règles 9-11) ; 409 si non autorisée ; 400 si motif manquant |
| POST | /tickets/{id}/comments | tous | multipart ; `kind` ; règle 11 (attente → cours) |
| GET | /tickets/{id}/events | tous | historique |
| POST | /tickets/{id}/ping | Digitalia | relance (commentaire + notification) |
| GET | /tickets/board?project=KEY | Digitalia | kanban : colonnes issues du workflow + cartes |
| GET | /tickets/export.csv | tous (scope) | mêmes filtres que la liste ; colonnes internes (facturation, devis…) pour Digitalia uniquement |

## Triage & devis
| GET | /triage | pm,admin | tickets nouveau/analyser tous projets |
| POST | /tickets/{id}/triage | pm,admin | `{decision: faire|analyser|attente|refuse|devis, type, priority, assignee, milestone, due_on, estimate_days, billing, message, quote:{amount_ht, parts, description, pdf}}` (règles 13-15) |
| GET | /tickets/{id}/quote | tous (scope) |
| POST | /tickets/{id}/quote/accept | client | règle 16 |
| POST | /tickets/{id}/quote/refuse | client | `{reason, attachments?}` règle 17 |
| PATCH | /tickets/{id}/quote | pm,admin | modifier (repasse en draft) ; POST /send pour renvoyer. PDF généré automatiquement si aucun n'est joint |

## Cockpit & équipe
| GET | /cockpit | Digitalia | par projet : santé + raison, compteurs ; « à traiter maintenant » (late, nouveau, attente, devis en attente, testint, test) ; charge par membre ; activité récente |
| GET | /team | Digitalia | membres actifs, tickets ouverts / en retard |
| GET | /activity[?project=KEY] | tous (scope) | « Ce qui a bougé » : 15 derniers événements des tickets visibles |

## Finances (admin)
| GET | /finance/overview?from=YYYY-MM&to=YYYY-MM | admin | par mois : recettes par projet, total, coûts, marge ; par projet : summary |
| GET/PUT | /finance/projects/{key} | admin | dev_price, licence, cost_mode… |
| GET/POST/PATCH/DELETE | /finance/projects/{key}/installments | admin | échéances dev ; `is_paid` |
| PATCH | /finance/quotes/{quote_id}/installments/{id} | admin | `is_paid` |
| GET/PUT | /finance/staff | admin | salaires + affectations |
| GET/PUT | /finance/settings | GET pm,admin (aide au chiffrage du triage) ; PUT admin | default_tjm |
| GET | /finance/export.csv?from=YYYY-MM&to=YYYY-MM | admin | recettes mois × projet, coûts, marge |

## Accès (admin)
| GET/POST/PATCH | /organizations | admin | clients ; POST crée le client + premier contact invité |
| GET/POST/PATCH | /users | admin | invitation (name, email, job ou organization), modification ; `?kind=digitalia|client` |
| POST | /users/{id}/activate, /deactivate, /resend-invite, /reset-password | admin | pas sur son propre compte |
| DELETE | /users/{id} | admin | RGPD : anonymisation (historique conservé) |
| PUT | /users/{id}/project-access | admin | liste de clés de projets |

## Réglages
| GET/PUT | /settings/notifications | pm,admin |

## Notifications
| GET | /notifications | tous | 30 dernières + `unread` |
| POST | /notifications/{id}/read, /notifications/read-all | tous | |

## Supervision
| GET | /health | public | `200` si base et broker OK, sinon `503` |
