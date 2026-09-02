from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe


@require_safe
def home(request):
    """Show the initial project status without accessing business data."""
    return render(request, "core/home.html")


@require_safe
@never_cache
def health(request):
    """Return a minimal liveness response without exposing internals."""
    return JsonResponse({"service": "formaflow", "status": "ok"})
