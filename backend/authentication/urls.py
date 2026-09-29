from django.urls import path

from authentication.views import (
    AcceptInviteView,
    InvitePreviewView,
    LoginView,
    MeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RefreshView,
    SignupView,
)

urlpatterns = [
    path("signup/", SignupView.as_view(), name="auth-signup"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("refresh/", RefreshView.as_view(), name="auth-refresh"),
    path("me/", MeView.as_view(), name="auth-me"),
    path("password-reset/", PasswordResetRequestView.as_view(), name="auth-password-reset"),
    path("password-reset/confirm/", PasswordResetConfirmView.as_view(), name="auth-password-reset-confirm"),
    path("invite/", InvitePreviewView.as_view(), name="auth-invite-preview"),
    path("invite/accept/", AcceptInviteView.as_view(), name="auth-invite-accept"),
]
