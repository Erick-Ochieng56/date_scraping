from __future__ import annotations

from django.conf import settings
from django.shortcuts import redirect


class SpaRedirectMixin:
    """
    When DJANGO_SERVE_SPA=1, legacy Django HTML dashboard pages redirect to the React app.
    Subclasses set `spa_redirect` or override `resolve_spa_redirect()`.
    """

    spa_redirect: str = "/"
    spa_redirect_pattern: str | None = None

    def resolve_spa_redirect(self) -> str:
        if self.spa_redirect_pattern:
            return self.spa_redirect_pattern.format(pk=self.kwargs.get("pk"))
        return self.spa_redirect

    def dispatch(self, request, *args, **kwargs):
        if getattr(settings, "SERVE_REACT_APP", False):
            return redirect(self.resolve_spa_redirect())
        return super().dispatch(request, *args, **kwargs)
