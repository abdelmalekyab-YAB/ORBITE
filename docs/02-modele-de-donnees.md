# 02 — Modèle de données (Django)

Tous les modèles ont `created_at`, `updated_at`. IDs : UUID ou BigAutoField, au choix (UUID recommandé pour l'API).

## Organisation et utilisateurs
```
Organization
  name            CharField(120)
  kind            Choice: 'digitalia' | 'client'          # une seule organisation 'digitalia'
  is_active       Bool

User (AbstractUser, login par email, username=email)
  organization    FK Organization
  job             Choice: 'admin' | 'pm' | 'dev' | 'client'   # 'client' pour toute organisation cliente
  is_active       Bool (désactivation)
  invited_at / activated_at   DateTime null              # invitation envoyée / première connexion
  color, initials  (dérivés, optionnel)

ProjectAccess          # quels projets un utilisateur CLIENT peut voir
  user   FK User ; project FK Project ; unique(user, project)
```
Les utilisateurs Digitalia voient tous les projets. Les clients ne voient que ceux de `ProjectAccess`, et seulement les
projets de leur organisation.

## Projets et versions
```
Project
  key             CharField(6) unique, majuscules (SCV, CHK…)
  name, description
  client          FK Organization (kind='client')
  lead            FK User (Digitalia)
  is_archived     Bool

Milestone (version de roadmap)
  project FK ; name ('Version 2.4') ; starts_on ; ends_on ; order
```

## Workflow (configurable)
```
WorkflowStatus
  project         FK Project null   # null = workflow global par défaut ; un projet peut avoir le sien (copie)
  key             slug ('nouveau', 'testint'…)
  label           CharField        # nom interne
  client_label    CharField        # étape vue par le client ('Reçue', 'Validation interne'…)
  ball            Choice 'digitalia' | 'client' | 'none'
  is_closed       Bool
  is_terminal_ok  Bool             # 'termine' : compte comme livré
  order           Int
  color           CharField (hex, optionnel)
  next            M2M WorkflowStatus (transitions autorisées)
  is_system       Bool             # nouveau/termine/refuse/annule non supprimables
```
Le workflow par défaut est chargé par une migration de données (voir `03-workflow.md`).

## Tickets
```
Ticket
  project         FK
  number          Int              # unique(project, number) ; identifiant affiché = f"{project.key}-{number}"
  type            Choice: 'bug' | 'evolution' | 'feature' | 'question' | 'support' | 'internal'
  title, description (Text)
  status          FK WorkflowStatus
  priority        Choice: 'low' | 'normal' | 'high' | 'critical'   # côté client affiché Confort/Gênant/Bloquant
  origin          Choice: 'client' | 'digitalia'
  is_internal     Bool             # jamais visible client
  author          FK User
  assignee        FK User null (Digitalia)
  milestone       FK Milestone null
  due_on          Date null
  parent          FK Ticket null (sous-tâche)
  billing         Choice: 'licence' | 'quote' | null    # décision de triage pour evolution/feature
  estimate_days   Decimal(5,1) null
  closed_at       DateTime null

Comment
  ticket FK ; author FK User ; body Text (peut être vide si pièces jointes) ; kind Choice 'comment'|'refusal'|'quote_refusal'|'reopen'
Attachment
  ticket FK ; comment FK null (null = joint à la création du ticket) ; file FileField ; content_type ; name ; uploaded_by
  # image/*, video/*, audio/* (message vocal webm), autres
TicketEvent (historique)
  ticket FK ; actor FK User null ; kind ('created','status','assignee','field','comment','quote_sent','quote_accepted','quote_refused'…)
  from_value, to_value (Text) ; message ; at
```

## Devis / proposition commerciale
```
Quote
  ticket          OneToOne Ticket
  amount_ht       Decimal(12,2)
  parts           Int 1|2|3            # 100 / 50-50 / 30-40-30
  description     Text
  pdf             FileField null
  status          Choice 'draft' | 'sent' | 'accepted' | 'refused'
  sent_at, decided_at, decided_by
QuoteInstallment
  quote FK ; due_on ; amount ; is_paid ; paid_on   # générées à l'acceptation
```

## Finances
```
ProjectFinance (OneToOne Project)
  dev_price          Decimal(12,2)
  licence_amount     Decimal(10,2)         # par mois
  licence_start      Date (1er du mois) null
  licence_end        Date null             # clôture de licence
  cost_mode          Choice 'none' | 'people' | 'monthly' | 'days'
  cost_monthly       Decimal null          # mode monthly
  cost_days, cost_tjm, cost_month  (mode days : coût unique comptabilisé ce mois-là)
DevInstallment
  finance FK ; due_on ; amount ; is_paid ; paid_on
StaffCost
  user FK (Digitalia) ; monthly_salary Decimal
StaffAllocation
  staff_cost FK ; project FK ; percent Int ; unique(staff_cost, project)
FinanceSettings (singleton) : default_tjm
```
Calculs (service `finance.py`, testés) :
- `revenue(project, month)` = échéances dev du mois + licence si `licence_start <= month <= licence_end|∞` + échéances de devis acceptés du mois
- `cost(project, month)` selon `cost_mode`
- `summary(project)` = encaissé dev / total dev, licence cumulée (mois × montant jusqu'au mois courant), évolutions vendues encaissées, reste à encaisser (dev + devis non payés), devis en attente (`sent`), coûts cumulés, marge.

## Notifications
```
NotificationSetting (par organisation Digitalia, singleton) : booléens par événement (voir 04)
Notification : user FK ; ticket FK null ; kind ; payload JSON ; sent_at ; read_at
```
