from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve

from config.views import spa_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("authentication.urls")),
    path("api/platform/", include("organizations.platform_urls")),
    path("api/org/", include("organizations.urls")),
    path("api/billing/", include("billing.urls")),
    path("api/employees/", include("employees.urls")),
    path("api/portal/", include("employees.portal_urls")),
    path("api/recognition/", include("recognition.urls")),
    path("api/attendance/", include("attendance.urls")),
    path("api/dashboard/", include("dashboard.urls")),
    path("api/payroll/", include("payroll.urls")),
    path("api/exits/", include("exits.urls")),
    path("api/approvals/", include("approvals.urls")),
    path("api/visitors/", include("visitors.urls")),
]

frontend_dist = settings.BASE_DIR.parent / "frontend" / "dist"
if frontend_dist.exists():
    urlpatterns += [
        re_path(r"^assets/(?P<path>.*)$", serve, {"document_root": frontend_dist / "assets"}),
        re_path(r"^(?!api/|admin/|media/).*$", spa_view, name="spa"),
    ]
else:
    from django.views.generic import TemplateView

    urlpatterns += [
        path("", TemplateView.as_view(template_name="index.html"), name="home"),
        path("enroll/<str:employee_id>/", TemplateView.as_view(template_name="enroll.html"), name="enroll"),
        path("monitor/", TemplateView.as_view(template_name="monitor.html"), name="monitor"),
    ]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
