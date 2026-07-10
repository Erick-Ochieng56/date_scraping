from __future__ import annotations

from django.contrib.auth import authenticate
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from dashboard.api.decorators import dashboard_api_view
from dashboard.api.permissions import IsDashboardPortalUser
from dashboard.permissions import scraper_group_name
from dashboard.utils import log_activity


def serialize_user_profile(user) -> dict:
    gname = scraper_group_name()
    scraper_group = Group.objects.filter(name=gname).first()
    if user.is_staff:
        role = "admin"
    elif scraper_group and user.groups.filter(id=scraper_group.id).exists():
        role = "staff"
    else:
        role = "none"
    return {
        "id": user.id,
        "username": user.get_username(),
        "email": user.email or "",
        "role": role,
        "is_superuser": bool(user.is_superuser),
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "date_joined": user.date_joined.isoformat() if getattr(user, "date_joined", None) else None,
    }


@dashboard_api_view(["GET", "PATCH"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def profile_detail(request: Request) -> Response:
    user = request.user

    if request.method == "GET":
        return Response({"success": True, "data": serialize_user_profile(user)})

    email = request.data.get("email")
    if email is None:
        return Response(
            {"success": False, "error": "No updatable fields provided."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    email = str(email).strip()
    if email != user.email:
        before_email = user.email
        user.email = email
        user.save(update_fields=["email"])
        log_activity(
            action="user_updated",
            object_type="user",
            object_id=user.id,
            description=f"Updated profile email for {user.get_username()}",
            user=user,
            metadata={"field": "email", "before": before_email, "after": user.email},
        )

    return Response({"success": True, "data": serialize_user_profile(user)})


@dashboard_api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDashboardPortalUser])
def profile_change_password(request: Request) -> Response:
    user = request.user
    current_password = request.data.get("current_password") or ""
    new_password = request.data.get("new_password") or ""

    if not current_password or not new_password:
        return Response(
            {"success": False, "error": "current_password and new_password are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not authenticate(username=user.get_username(), password=current_password):
        return Response(
            {"success": False, "error": "Current password is incorrect."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        validate_password(new_password, user=user)
    except ValidationError as exc:
        return Response(
            {"success": False, "error": " ".join(exc.messages)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user.set_password(new_password)
    user.save(update_fields=["password"])
    log_activity(
        action="user_updated",
        object_type="user",
        object_id=user.id,
        description=f"Password changed for {user.get_username()}",
        user=user,
        metadata={"field": "password"},
    )
    return Response({"success": True, "data": {"message": "Password updated."}})
