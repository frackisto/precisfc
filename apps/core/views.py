from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


@require_GET
@never_cache
def healthz(request):
    """Sonde de disponibilité de l'application (sans accès à la base de données)."""
    return JsonResponse({"status": "ok"})
