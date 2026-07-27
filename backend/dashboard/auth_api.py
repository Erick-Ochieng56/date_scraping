from __future__ import annotations

import json

from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.contrib.auth.password_validation import validate_password
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from dashboard.permissions import scraper_group_name


def _user_role(user) -> str | None:
    """Same admin/staff/no-access classification used by login/me."""
    if user.is_staff:
        return "admin"
    if user.groups.filter(name=scraper_group_name()).exists():
        return "staff"
    return None


@require_POST
def api_auth_login(request: HttpRequest) -> JsonResponse:
    """Session login for SPA users (staff and admin)."""
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)

    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    if not username:
        return JsonResponse(
            {"success": False, "error": "Username is required."}, status=400
        )

    user = authenticate(request, username=username, password=password)
    if user is None or not user.is_active:
        return JsonResponse(
            {"success": False, "error": "Invalid username or password."}, status=400
        )

    gname = scraper_group_name()
    is_admin = bool(user.is_staff)
    is_staff_portal = user.groups.filter(name=gname).exists()
    if not is_admin and not is_staff_portal:
        return JsonResponse(
            {
                "success": False,
                "error": "Your account is not enabled for the staff dashboard.",
            },
            status=403,
        )

    login(request, user)
    return JsonResponse(
        {
            "success": True,
            "user": {"username": user.get_username(), "role": "admin" if is_admin else "staff"},
        }
    )


@require_POST
def api_auth_logout(request: HttpRequest) -> JsonResponse:
    # Idempotent logout: if the session is already anonymous/expired, still return success.
    if request.user.is_authenticated:
        logout(request)
    return JsonResponse({"success": True})


@ensure_csrf_cookie
@require_GET
def api_auth_me(request: HttpRequest) -> JsonResponse:
    """Return session + role for the SPA; sets CSRF cookie when needed."""
    if not request.user.is_authenticated:
        return JsonResponse({"authenticated": False})

    if request.user.is_staff:
        return JsonResponse(
            {
                "authenticated": True,
                "role": "admin",
                "username": request.user.get_username(),
            }
        )

    if request.user.groups.filter(name=scraper_group_name()).exists():
        return JsonResponse(
            {
                "authenticated": True,
                "role": "staff",
                "username": request.user.get_username(),
            }
        )

    # Stale session (e.g. Django admin user without portal group) — clear so API calls get 401, not 403.
    logout(request)
    return JsonResponse(
        {
            "authenticated": False,
            "reason": "no_portal_access",
        }
    )


def _profile_payload(user) -> dict:
    return {
        "id": user.id,
        "username": user.get_username(),
        "email": user.email or "",
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "role": _user_role(user),
        "date_joined": user.date_joined.isoformat() if user.date_joined else None,
        "last_login": user.last_login.isoformat() if user.last_login else None,
    }


@require_http_methods(["GET", "PATCH"])
def api_auth_profile(request: HttpRequest) -> JsonResponse:
    """View/edit the logged-in user's own account. Username/role are not editable here
    — those stay admin-managed via Admin -> Users, same as account creation/activation."""
    if not request.user.is_authenticated:
        return JsonResponse({"success": False, "error": "Authentication required."}, status=401)

    if request.method == "GET":
        return JsonResponse({"success": True, "data": _profile_payload(request.user)})

    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)

    user = request.user
    if "email" in body:
        email = (body.get("email") or "").strip()
        if email:
            try:
                validate_email(email)
            except ValidationError:
                return JsonResponse({"success": False, "error": "Enter a valid email address."}, status=400)
        user.email = email
    if "first_name" in body:
        user.first_name = (body.get("first_name") or "").strip()[:150]
    if "last_name" in body:
        user.last_name = (body.get("last_name") or "").strip()[:150]

    user.save(update_fields=["email", "first_name", "last_name"])
    return JsonResponse({"success": True, "data": _profile_payload(user)})


@require_POST
def api_auth_change_password(request: HttpRequest) -> JsonResponse:
    """Self-service password change. Keeps the current session alive on success
    (update_session_auth_hash) so the user isn't immediately logged out."""
    if not request.user.is_authenticated:
        return JsonResponse({"success": False, "error": "Authentication required."}, status=401)

    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)

    current_password = body.get("current_password") or ""
    new_password = body.get("new_password") or ""

    user = request.user
    if not user.check_password(current_password):
        return JsonResponse({"success": False, "error": "Current password is incorrect."}, status=400)

    if not new_password:
        return JsonResponse({"success": False, "error": "New password is required."}, status=400)

    try:
        validate_password(new_password, user=user)
    except ValidationError as exc:
        return JsonResponse({"success": False, "error": " ".join(exc.messages)}, status=400)

    user.set_password(new_password)
    user.save(update_fields=["password"])
    update_session_auth_hash(request, user)
    return JsonResponse({"success": True})
