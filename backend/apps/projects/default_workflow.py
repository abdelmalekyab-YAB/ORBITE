"""Workflow par défaut (docs/03-workflow.md). Utilisé par la migration de données et, plus tard, par /workflow/reset."""

# key, label, client_label, ball, is_closed, is_terminal_ok, next
DEFAULT_WORKFLOW = [
    ("nouveau", "Nouveau", "Reçue", "digitalia", False, False, ["analyser", "faire", "devis", "refuse"]),
    ("analyser", "À analyser", "Reçue", "digitalia", False, False, ["faire", "devis", "attente", "refuse"]),
    ("devis", "Devis à valider", "Proposition à valider", "client", False, False, ["faire", "refuse", "analyser"]),
    ("faire", "À faire", "Planifiée", "digitalia", False, False, ["cours", "annule"]),
    ("cours", "En cours", "En développement", "digitalia", False, False, ["testint", "attente", "faire"]),
    ("testint", "Test interne", "Validation interne", "digitalia", False, False, ["test", "cours"]),
    ("attente", "En attente client", "En développement", "client", False, False, ["cours", "annule"]),
    ("test", "Test client", "À tester", "client", False, False, ["termine", "cours"]),
    ("termine", "Terminé", "Livrée", "none", True, True, ["cours"]),
    ("refuse", "Refusé", "Clôturée", "none", True, False, ["analyser"]),
    ("annule", "Annulé", "Clôturée", "none", True, False, ["faire"]),
]
SYSTEM_KEYS = {"nouveau", "termine", "refuse", "annule"}
COLORS = {"nouveau": "#3de1ff", "analyser": "#a855f7", "devis": "#ffc14d", "faire": "#c5bde0", "cours": "#e04bff",
          "testint": "#7c3aed", "attente": "#ffc14d", "test": "#3dffb7", "termine": "#3dffb7", "refuse": "#ff6b8a",
          "annule": "#8b83ab"}


def load_default_workflow(WorkflowStatus, project=None):
    """Crée (ou recrée) le workflow par défaut. Accepte le modèle historique d'une migration."""
    WorkflowStatus.objects.filter(project=project).delete()
    created = {}
    for order, (key, label, client_label, ball, closed, ok, _next) in enumerate(DEFAULT_WORKFLOW, start=1):
        created[key] = WorkflowStatus.objects.create(
            project=project, key=key, label=label, client_label=client_label, ball=ball, is_closed=closed,
            is_terminal_ok=ok, order=order, color=COLORS[key], is_system=key in SYSTEM_KEYS)
    for key, *_rest, nxt in DEFAULT_WORKFLOW:
        created[key].next.set([created[n] for n in nxt])
    return created
