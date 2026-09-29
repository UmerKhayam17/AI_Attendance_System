from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from authentication.serializers import (
    AcceptInviteSerializer,
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RefreshSerializer,
    SignupSerializer,
    check_reset_token,
    decode_uid,
    encode_uid,
    make_reset_token,
)
from authentication.tokens import issue_tokens
from organizations.models import Invite, Membership, Organization
from organizations.serializers import OrganizationSerializer, user_payload


def _auth_response(user) -> dict:
    membership = (
        Membership.objects.select_related("organization").filter(user=user).first()
    )
    payload = user_payload(user, membership)
    payload.update(issue_tokens(user))
    return payload


class SignupView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = User.objects.create_user(
            username=data["email"],
            email=data["email"],
            password=data["password"],
            first_name=data["first_name"],
            last_name=data.get("last_name") or "",
        )
        org = Organization.objects.create(
            name=data["organization_name"],
            org_type=data["org_type"],
            created_via="signup",
            billing_exempt=False,
        )
        Membership.objects.create(
            user=user,
            organization=org,
            role=Membership.ROLE_OWNER,
        )
        return Response(_auth_response(user), status=status.HTTP_201_CREATED)


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].lower().strip()
        password = serializer.validated_data["password"]
        user = (
            User.objects.filter(username__iexact=email).first()
            or User.objects.filter(email__iexact=email).first()
        )
        if not user or not user.check_password(password):
            return Response(
                {"error": "Invalid email or password"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not user.is_active:
            return Response(
                {"error": "Account is disabled"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not user.is_superuser and not user.memberships.exists():
            return Response(
                {"error": "No organization membership for this account"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(_auth_response(user))


class RefreshView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            refresh = RefreshToken(serializer.validated_data["refresh"])
            user = User.objects.filter(pk=refresh["user_id"]).first()
            if not user or not user.is_active:
                raise TokenError("Invalid user")
            return Response(issue_tokens(user))
        except TokenError:
            return Response(
                {"error": "Invalid or expired refresh token"},
                status=status.HTTP_401_UNAUTHORIZED,
            )


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        membership = getattr(request, "membership", None)
        if membership is None:
            membership = (
                Membership.objects.select_related("organization")
                .filter(user=request.user)
                .first()
            )
        return Response(user_payload(request.user, membership))


class PasswordResetRequestView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].lower().strip()
        user = (
            User.objects.filter(username__iexact=email).first()
            or User.objects.filter(email__iexact=email).first()
        )
        # Always succeed to avoid account enumeration
        if user:
            uid = encode_uid(user)
            token = make_reset_token(user)
            base = getattr(settings, "FRONTEND_URL", "http://localhost:5173").rstrip("/")
            link = f"{base}/reset-password?uid={uid}&token={token}"
            send_mail(
                subject="Reset your AI Attendance password",
                message=f"Open this link to reset your password:\n{link}",
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@localhost"),
                recipient_list=[user.email or email],
                fail_silently=True,
            )
            if settings.DEBUG:
                return Response({"detail": "If the email exists, a reset link was sent.", "debug_link": link})
        return Response({"detail": "If the email exists, a reset link was sent."})


class PasswordResetConfirmView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = decode_uid(serializer.validated_data["uid"])
        if not user or not check_reset_token(user, serializer.validated_data["token"]):
            return Response(
                {"error": "Invalid or expired reset link"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.set_password(serializer.validated_data["password"])
        user.save(update_fields=["password"])
        return Response({"detail": "Password updated"})


class InvitePreviewView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        token = request.query_params.get("token", "")
        invite = Invite.objects.filter(token=token).select_related("organization").first()
        if not invite or not invite.is_valid:
            return Response(
                {"error": "Invite is invalid or expired"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({
            "email": invite.email,
            "role": invite.role,
            "organization": OrganizationSerializer(invite.organization).data,
        })


class AcceptInviteView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AcceptInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invite = Invite.objects.select_related("organization", "employee").get(
            token=serializer.validated_data["token"]
        )
        if not invite.is_valid:
            return Response(
                {"error": "Invite is invalid or expired"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = invite.email.lower().strip()
        user = User.objects.filter(username__iexact=email).first()
        if user:
            if user.memberships.exists():
                return Response(
                    {"error": "This email already belongs to another organization"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user.set_password(serializer.validated_data["password"])
            user.first_name = serializer.validated_data["first_name"]
            user.last_name = serializer.validated_data.get("last_name") or ""
            user.is_active = True
            user.save()
        else:
            user = User.objects.create_user(
                username=email,
                email=email,
                password=serializer.validated_data["password"],
                first_name=serializer.validated_data["first_name"],
                last_name=serializer.validated_data.get("last_name") or "",
            )

        Membership.objects.create(
            user=user,
            organization=invite.organization,
            role=invite.role,
        )
        if invite.role == Membership.ROLE_EMPLOYEE:
            from employees.models import Employee

            person = invite.employee
            if person is None:
                person = Employee.objects.filter(
                    organization=invite.organization,
                    email__iexact=email,
                ).first()
            if person and person.user_id is None:
                person.user = user
                person.save(update_fields=["user", "updated_at"])
        elif invite.role == Membership.ROLE_PARENT and invite.employee_id:
            from employees.models import ParentLink

            ParentLink.objects.get_or_create(user=user, employee=invite.employee)
        invite.accepted_at = timezone.now()
        invite.save(update_fields=["accepted_at"])
        return Response(_auth_response(user), status=status.HTTP_201_CREATED)
