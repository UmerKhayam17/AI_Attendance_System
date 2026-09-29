from pathlib import Path

from django.conf import settings
from django.http import Http404, HttpResponse
from django.views.decorators.cache import never_cache


@never_cache
def spa_view(request, *_args, **_kwargs):
    index_path = settings.BASE_DIR.parent / 'frontend' / 'dist' / 'index.html'
    if not index_path.exists():
        raise Http404("Frontend build not found. Run: cd frontend && npm run build")
    return HttpResponse(index_path.read_text(encoding='utf-8'), content_type='text/html')
