"""Format d'erreur unique de l'API : { "detail": "...", "code": "..." } (docs/05-api.md)."""
from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None
    data = response.data
    if isinstance(data, dict) and "detail" in data:
        detail = data["detail"]
        code = getattr(detail, "code", None) or getattr(exc, "default_code", "error")
        response.data = {"detail": str(detail), "code": code}
    else:  # erreurs de validation de champs
        response.data = {"detail": "Données invalides.", "code": "invalid", "fields": data}
    return response
