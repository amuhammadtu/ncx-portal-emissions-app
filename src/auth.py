"""
IAP JWT Verification & Entra ID Workforce Identity Federation Middleware (`ENG-2080`).

Cryptographically validates the `X-Goog-IAP-Jwt-Assertion` ES256 JWT header injected by
Google Cloud Run Direct IAP against Google's public JWK set. Enforces defence-in-depth
role-based access control via `@require_group` and populates `st.session_state.user`.
"""

from __future__ import annotations

import functools
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

import streamlit as st
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from src.telemetry import compute_user_hash, log_structured_event

IAP_CERTS_URL = "https://www.gstatic.com/iap/verify/public_key-jwk"
IAP_ISSUER = "https://cloud.google.com/iap"
DEFAULT_WORKFORCE_POOL = (
    "locations/global/workforcePools/agentspace-entra-id-p-oidc-exnat"
)
DEFAULT_ALLOWED_GROUPS = (
    "group:tu-asset-management-engineers@transurban.com",
    "group:tu-tunnel-operations-analysts@transurban.com",
    "group:tu-seal-platform-admins@transurban.com",
)


class IAPAuthenticationError(PermissionError):
    """Raised when the X-Goog-IAP-Jwt-Assertion header is missing, forged, or invalid."""


class IAPAuthorizationError(PermissionError):
    """Raised when an authenticated principal lacks the required Entra ID group claim."""


@dataclass(frozen=True)
class IAPUser:
    """Verified user identity extracted from Cloud Run Direct IAP JWT assertion."""

    email: str
    sub: str
    groups: tuple[str, ...] = field(default_factory=tuple)
    user_hash: str = ""
    auth_mode: str = "iap_jwt"
    workforce_pool: str = DEFAULT_WORKFORCE_POOL
    access_token: str | None = None
    trace_context: str | None = None
    raw_claims: Mapping[str, Any] = field(default_factory=dict)


def verify_iap_jwt(
    jwt_assertion: str | None,
    expected_audience: str | None = None,
) -> dict[str, Any]:
    """
    Cryptographically verify the ES256 `X-Goog-IAP-Jwt-Assertion` token (`ENG-2080`).

    Parameters
    ----------
    jwt_assertion : str | None
        Raw JWT string from `X-Goog-IAP-Jwt-Assertion`.
    expected_audience : str | None
        Expected IAP audience string (`/projects/{PROJECT_NUMBER}/global/backendServices/{SERVICE_ID}`
        or `/projects/{PROJECT_NUMBER}/apps/{PROJECT_ID}`). Defaults to `os.environ["IAP_AUDIENCE"]`.

    Returns
    -------
    dict[str, Any]
        Decoded and cryptographically verified JWT claims.

    Raises
    ------
    IAPAuthenticationError
        If the assertion is missing, expired, signed with an untrusted key, has a
        mismatched audience, or was not issued by `https://cloud.google.com/iap`.
    """
    if not jwt_assertion or not jwt_assertion.strip():
        raise IAPAuthenticationError(
            "Missing X-Goog-IAP-Jwt-Assertion header. Direct container access outside IAP is prohibited."
        )

    audience = (expected_audience or os.environ.get("IAP_AUDIENCE", "")).strip()
    if not audience:
        raise IAPAuthenticationError(
            "IAP_AUDIENCE environment variable is not configured for JWT verification."
        )

    try:
        request_adapter = google_requests.Request()
        decoded_claims: dict[str, Any] = id_token.verify_token(
            jwt_assertion.strip(),
            request_adapter,
            audience=audience,
            certs_url=IAP_CERTS_URL,
        )
    except Exception as exc:
        raise IAPAuthenticationError(
            f"IAP JWT cryptographic verification failed: {exc}"
        ) from exc

    issuer = decoded_claims.get("iss")
    if issuer != IAP_ISSUER:
        raise IAPAuthenticationError(
            f"Invalid IAP JWT issuer '{issuer}'. Expected '{IAP_ISSUER}'."
        )

    sub = decoded_claims.get("sub")
    email = decoded_claims.get("email")
    if not sub or not email:
        raise IAPAuthenticationError(
            "IAP JWT assertion is missing required 'sub' or 'email' identity claims."
        )

    return decoded_claims


def _extract_groups_from_claims(claims: Mapping[str, Any]) -> tuple[str, ...]:
    """Extract normalized `group:...` bindings from Workforce Identity Federation claims."""
    raw_groups: list[str] = []
    for key in ("groups", "google", "gcip"):
        val = claims.get(key)
        if isinstance(val, list):
            raw_groups.extend(str(item) for item in val)
        elif isinstance(val, dict):
            nested = val.get("groups", [])
            if isinstance(nested, list):
                raw_groups.extend(str(item) for item in nested)

    normalized: list[str] = []
    for grp in raw_groups:
        grp_clean = grp.strip().lower()
        if not grp_clean:
            continue
        if not grp_clean.startswith("group:"):
            grp_clean = f"group:{grp_clean}"
        if grp_clean not in normalized:
            normalized.append(grp_clean)
    return tuple(normalized)


def is_cloud_run_environment() -> bool:
    """Return True when executing inside a Cloud Run container or when strict IAP is forced."""
    if os.environ.get("REQUIRE_IAP_JWT", "").strip().lower() in ("1", "true", "yes"):
        return True
    return bool(os.environ.get("K_SERVICE"))


def resolve_user_from_headers(
    headers: Mapping[str, str] | None = None,
    *,
    expected_audience: str | None = None,
) -> IAPUser:
    """
    Resolve and verify the current user from HTTP headers (`st.context.headers`).

    - In Cloud Run (`K_SERVICE` set or `REQUIRE_IAP_JWT=true`), strictly requires and
      cryptographically verifies `X-Goog-IAP-Jwt-Assertion`. Never trusts unverified
      `X-Goog-Authenticated-User-Email` headers alone (`ENG-2080`).
    - In local / Cloud Workstation development (`K_SERVICE` unset and `ALLOW_LOCAL_DEV_AUTH != false`),
      if `X-Goog-IAP-Jwt-Assertion` is present it is verified; otherwise falls back to a clearly
      badged local developer principal so inner-loop previews and `AppTest` work seamlessly.
    """
    hdrs: dict[str, str] = {
        k.lower(): v for k, v in (headers or {}).items() if isinstance(k, str) and isinstance(v, str)
    }
    jwt_assertion = hdrs.get("x-goog-iap-jwt-assertion")
    trace_ctx = hdrs.get("x-cloud-trace-context")
    access_token = hdrs.get("x-goog-iap-access-token") or hdrs.get("x-forwarded-access-token")

    if jwt_assertion or is_cloud_run_environment():
        claims = verify_iap_jwt(jwt_assertion, expected_audience=expected_audience)
        email = str(claims["email"]).strip().lower()
        sub = str(claims["sub"]).strip()
        groups = _extract_groups_from_claims(claims)
        if not groups:
            # Default group fallback when Entra OIDC claim mapping is configured at backendService IAM level
            configured_default = os.environ.get(
                "IAP_DEFAULT_VERIFIED_GROUP",
                "group:tu-asset-management-engineers@transurban.com",
            )
            groups = (configured_default.strip().lower(),)

        user_hash = compute_user_hash(email)
        log_structured_event(
            "Verified Cloud Run Direct IAP JWT assertion",
            severity="INFO",
            user_hash=user_hash,
            trace_context=trace_ctx,
            extra={"auth_mode": "iap_jwt", "sub": sub, "group_count": len(groups)},
        )
        return IAPUser(
            email=email,
            sub=sub,
            groups=groups,
            user_hash=user_hash,
            auth_mode="iap_jwt",
            workforce_pool=DEFAULT_WORKFORCE_POOL,
            access_token=access_token,
            trace_context=trace_ctx,
            raw_claims=claims,
        )

    # Local / Cloud Workstation Developer Inner-Loop Fallback
    allow_local = os.environ.get("ALLOW_LOCAL_DEV_AUTH", "true").strip().lower() not in (
        "0",
        "false",
        "no",
    )
    if not allow_local:
        raise IAPAuthenticationError(
            "Local dev authentication is disabled and no X-Goog-IAP-Jwt-Assertion header was provided."
        )

    dev_email = os.environ.get("LOCAL_DEV_USER_EMAIL", "amuhammad@transurban.com").strip().lower()
    dev_sub = f"{DEFAULT_WORKFORCE_POOL}/subject/{dev_email}"
    dev_groups = DEFAULT_ALLOWED_GROUPS
    user_hash = compute_user_hash(dev_email)

    return IAPUser(
        email=dev_email,
        sub=dev_sub,
        groups=dev_groups,
        user_hash=user_hash,
        auth_mode="local_workstation_dev",
        workforce_pool=DEFAULT_WORKFORCE_POOL,
        access_token=access_token,
        trace_context=trace_ctx,
        raw_claims={"iss": "local-dev", "email": dev_email, "sub": dev_sub, "groups": list(dev_groups)},
    )


def get_current_user() -> IAPUser:
    """
    Retrieve the verified `IAPUser` from `st.context.headers` and cache in `st.session_state.user`.
    """
    raw_headers: dict[str, str] = {}
    try:
        ctx_headers = getattr(st.context, "headers", None)
        if ctx_headers:
            raw_headers = dict(ctx_headers)
    except Exception:
        raw_headers = {}

    user = resolve_user_from_headers(raw_headers)
    st.session_state["user"] = user
    return user


def check_user_group_access(user: IAPUser, allowed_groups: tuple[str, ...]) -> bool:
    """Return True if `user.groups` intersects with `allowed_groups` (case-insensitive)."""
    if not allowed_groups:
        return True
    normalized_allowed = {
        g.strip().lower() if g.strip().lower().startswith("group:") else f"group:{g.strip().lower()}"
        for g in allowed_groups
    }
    user_groups = {g.strip().lower() for g in user.groups}
    return bool(user_groups.intersection(normalized_allowed))


def require_group(*allowed_groups: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator enforcing Entra ID Workforce Identity Pool group membership (`ENG-2080`).

    Logs structured `WARNING` events to Cloud Logging on any authentication or authorization
    failure and halts Streamlit execution cleanly with `st.error` + `st.stop()`.
    """
    effective_groups = allowed_groups or DEFAULT_ALLOWED_GROUPS

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                user = get_current_user()
            except IAPAuthenticationError as auth_err:
                log_structured_event(
                    f"IAP authentication rejected: {auth_err}",
                    severity="WARNING",
                    user_hash="unauthenticated",
                    extra={"event_type": "auth_failure"},
                )
                st.error(f"🔒 **IAP Authentication Required (`ENG-2080`)**: {auth_err}")
                st.stop()
                return None

            if not check_user_group_access(user, effective_groups):
                log_structured_event(
                    f"Unauthorized group access attempt by user_hash={user.user_hash}",
                    severity="WARNING",
                    user_hash=user.user_hash,
                    trace_context=user.trace_context,
                    extra={
                        "event_type": "rbac_denied",
                        "required_groups": list(effective_groups),
                        "user_groups": list(user.groups),
                    },
                )
                st.error(
                    "🚫 **Access Denied (`ENG-2080` Defence-in-Depth RBAC)**: "
                    f"Principal `{user.email}` is not a member of the required Entra ID group(s): "
                    f"`{', '.join(effective_groups)}`."
                )
                st.stop()
                return None

            return func(*args, **kwargs)

        return wrapper

    return decorator
