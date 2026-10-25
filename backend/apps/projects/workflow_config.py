"""Configuration du workflow (docs/03-workflow.md, « Configurabilité »).
Remplacer la config, personnaliser par projet, réinitialiser."""
from django.db import transaction
from django.utils.text import slugify
from rest_framework import status
from rest_framework.exceptions import APIException

from .default_workflow import COLORS, DEFAULT_WORKFLOW, SYSTEM_KEYS
from .models import Project, WorkflowStatus


class WorkflowConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "workflow_conflict"


class WorkflowInvalid(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "workflow_invalid"


def default_spec() -> list[dict]:
    return [{"key": k, "label": label, "client_label": cl, "ball": ball, "is_closed": closed, "is_terminal_ok": ok,
             "color": COLORS[k], "next": nxt} for k, label, cl, ball, closed, ok, nxt in DEFAULT_WORKFLOW]


def _tickets_using(status_obj: WorkflowStatus, project: Project | None):
    from apps.tickets.models import Ticket

    qs = Ticket.objects.filter(status=status_obj)
    return qs.filter(project=project) if project else qs


def _validate(spec: list[dict]) -> list[dict]:
    if not isinstance(spec, list) or not spec:
        raise WorkflowInvalid("Le workflow doit contenir au moins un statut.")
    clean, keys = [], set()
    for item in spec:
        key = slugify(str(item.get("key") or item.get("label") or ""))[:30]
        if not key or key in keys:
            raise WorkflowInvalid(f"Clé de statut manquante ou en double : « {key or '?'} ».")
        if not str(item.get("label", "")).strip():
            raise WorkflowInvalid(f"Le statut « {key} » doit avoir un nom.")
        ball = item.get("ball", "digitalia")
        if ball not in ("digitalia", "client", "none"):
            raise WorkflowInvalid(f"Balle inconnue pour « {key} ».")
        keys.add(key)
        clean.append({**item, "key": key, "ball": ball})
    missing = SYSTEM_KEYS - keys
    if missing:
        raise WorkflowConflict(f"Statuts système obligatoires : {', '.join(sorted(missing))}.")
    for item in clean:
        unknown = set(item.get("next", [])) - keys
        if unknown:
            raise WorkflowInvalid(f"Transition vers un statut inconnu : {', '.join(sorted(unknown))}.")
    return clean


def _customize(project: Project) -> None:
    """Premier « personnaliser » : copie du workflow global vers le projet, tickets du projet rebranchés."""
    from apps.tickets.models import Ticket

    if WorkflowStatus.objects.filter(project=project).exists():
        return
    globals_ = list(WorkflowStatus.objects.filter(project__isnull=True).prefetch_related("next"))
    copies = {}
    for g in globals_:
        copies[g.key] = WorkflowStatus.objects.create(
            project=project, key=g.key, label=g.label, client_label=g.client_label, ball=g.ball,
            is_closed=g.is_closed, is_terminal_ok=g.is_terminal_ok, order=g.order, color=g.color,
            is_system=g.is_system)
    for g in globals_:
        copies[g.key].next.set([copies[n.key] for n in g.next.all()])
    for g in globals_:
        Ticket.objects.filter(project=project, status=g).update(status=copies[g.key])


@transaction.atomic
def apply_workflow(project: Project | None, spec: list[dict]) -> list[WorkflowStatus]:
    spec = _validate(spec)
    if project is not None:
        _customize(project)
    existing = {s.key: s for s in WorkflowStatus.objects.filter(project=project)}
    wanted = {item["key"] for item in spec}
    for key, st in existing.items():
        if key in wanted:
            continue
        if st.is_system:
            raise WorkflowConflict(f"Le statut « {st.label} » est un statut système : il ne peut pas être supprimé.")
        used = _tickets_using(st, project).count()
        if used:
            raise WorkflowConflict(f"Le statut « {st.label} » est utilisé par {used} ticket{'s' if used > 1 else ''}.")
    for key in set(existing) - wanted:
        existing[key].delete()
    saved: dict[str, WorkflowStatus] = {}
    for order, item in enumerate(spec, start=1):
        st = existing.get(item["key"]) or WorkflowStatus(project=project, key=item["key"])
        st.label = item["label"].strip()
        st.client_label = (item.get("client_label") or item["label"]).strip()
        st.ball = "none" if item.get("is_closed") else item["ball"]
        st.is_closed = bool(item.get("is_closed"))
        st.is_terminal_ok = bool(item.get("is_terminal_ok"))
        st.color = item.get("color") or COLORS.get(item["key"], "#a855f7")
        st.is_system = item["key"] in SYSTEM_KEYS
        st.order = order
        st.save()
        saved[st.key] = st
    for item in spec:
        saved[item["key"]].next.set([saved[k] for k in item.get("next", []) if k != item["key"]])
    return list(saved.values())


@transaction.atomic
def reset_workflow(project: Project | None) -> None:
    """Revenir au workflow par défaut. Pour un projet : abandon de la personnalisation (retour au global)."""
    from apps.tickets.models import Ticket

    if project is None:
        apply_workflow(None, default_spec())
        return
    custom = list(WorkflowStatus.objects.filter(project=project))
    globals_ = {s.key: s for s in WorkflowStatus.objects.filter(project__isnull=True)}
    for st in custom:
        used = Ticket.objects.filter(project=project, status=st)
        if st.key not in globals_ and used.exists():
            raise WorkflowConflict(f"Le statut « {st.label} » est utilisé par {used.count()} ticket(s) et n'existe "
                                   "pas dans le workflow par défaut.")
        if st.key in globals_:
            used.update(status=globals_[st.key])
    WorkflowStatus.objects.filter(project=project).delete()
