"""Require X-API-Key when AI_ATTENDANCE_API_KEY (or INTEGRATION_API_KEY) is set."""
from django.conf import settings


class ApiKeyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.api_key = (
            getattr(settings, "INTEGRATION_API_KEY", "")
            or getattr(settings, "AI_ATTENDANCE_API_KEY", "")
            or ""
        ).strip()

    def __call__(self, request):
        path = request.path or ""
        if self.api_key and path.startswith("/api/"):
            provided = request.headers.get("X-API-Key") or request.META.get("HTTP_X_API_KEY", "")
            if provided != self.api_key:
                from django.http import JsonResponse

                return JsonResponse({"error": "Invalid or missing API key"}, status=401)
        return self.get_response(request)
