from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import serializers

from organizations.models import Invite, Organization


class SignupSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    organization_name = serializers.CharField(max_length=200)
    org_type = serializers.ChoiceField(
        choices=[Organization.TYPE_COMPANY, Organization.TYPE_SCHOOL],
        default=Organization.TYPE_COMPANY,
    )

    def validate_email(self, value):
        email = value.lower().strip()
        if User.objects.filter(username__iexact=email).exists() or User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("An account with this email already exists")
        return email

    def validate_password(self, value):
        validate_password(value)
        return value


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    password = serializers.CharField(write_only=True, min_length=8)

    def validate_password(self, value):
        validate_password(value)
        return value


class AcceptInviteSerializer(serializers.Serializer):
    token = serializers.CharField()
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate_token(self, value):
        invite = Invite.objects.filter(token=value).select_related("organization").first()
        if not invite or not invite.is_valid:
            raise serializers.ValidationError("Invite is invalid or expired")
        return value


class RefreshSerializer(serializers.Serializer):
    refresh = serializers.CharField()


def encode_uid(user: User) -> str:
    return urlsafe_base64_encode(force_bytes(user.pk))


def decode_uid(uid: str) -> User | None:
    try:
        user_id = force_str(urlsafe_base64_decode(uid))
        return User.objects.filter(pk=user_id).first()
    except (ValueError, TypeError, OverflowError):
        return None


def make_reset_token(user: User) -> str:
    return default_token_generator.make_token(user)


def check_reset_token(user: User, token: str) -> bool:
    return default_token_generator.check_token(user, token)
