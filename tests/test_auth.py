"""Unit tests for Zero-Trust IAP JWT verification and Entra ID RBAC (`ENG-2080`).

Compatible with both `python -m unittest discover -s tests -v` and `pytest`.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from src.auth import (
    DEFAULT_ALLOWED_GROUPS,
    DEFAULT_WORKFORCE_POOL,
    IAPAuthenticationError,
    IAPUser,
    IAP_ISSUER,
    _extract_groups_from_claims,
    check_user_group_access,
    resolve_user_from_headers,
    verify_iap_jwt,
)


class TestIAPZeroTrustAuth(unittest.TestCase):
    """Test suite for ENG-2080 Zero-Trust IAP & Workforce Identity RBAC."""

    def test_missing_iap_jwt_raises_error(self) -> None:
        """Missing X-Goog-IAP-Jwt-Assertion header must fail closed."""
        with self.assertRaisesRegex(IAPAuthenticationError, "Missing X-Goog-IAP-Jwt-Assertion"):
            verify_iap_jwt("", expected_audience="/projects/123/apps/ncx")

    def test_forged_or_malformed_iap_jwt_raises_error(self) -> None:
        """Forged or malformed JWT tokens must be rejected by ES256 verification."""
        with self.assertRaisesRegex(IAPAuthenticationError, "IAP JWT cryptographic verification failed"):
            verify_iap_jwt("eyJhbGciOiJFUzI1NiJ9.forged.signature", expected_audience="/projects/123/apps/ncx")

    def test_valid_mocked_iap_jwt_extracts_workforce_claims(self) -> None:
        """Valid ES256 IAP claims must populate IAPUser and Entra ID groups."""
        mock_claims = {
            "iss": IAP_ISSUER,
            "sub": f"{DEFAULT_WORKFORCE_POOL}/subject/amuhammad@transurban.com",
            "email": "amuhammad@transurban.com",
            "aud": "/projects/123/global/backendServices/456",
            "google": {
                "groups": [
                    "group:tu-asset-management-engineers@transurban.com",
                    "group:tu-tunnel-operations-analysts@transurban.com",
                ]
            },
        }
        with patch("src.auth.id_token.verify_token", return_value=mock_claims):
            user = resolve_user_from_headers(
                {"x-goog-iap-jwt-assertion": "valid.jwt.token"},
                expected_audience="/projects/123/global/backendServices/456",
            )
            self.assertIsInstance(user, IAPUser)
            self.assertEqual(user.email, "amuhammad@transurban.com")
            self.assertTrue(check_user_group_access(user, DEFAULT_ALLOWED_GROUPS))
            self.assertFalse(check_user_group_access(user, ("group:unauthorized@transurban.com",)))
            self.assertEqual(user.auth_mode, "iap_jwt")

    def test_extract_groups_normalizes_group_prefix(self) -> None:
        """Group extraction must normalize group strings to `group:...` lowercase."""
        claims = {"groups": ["tu-asset-management-engineers@transurban.com"]}
        self.assertEqual(
            _extract_groups_from_claims(claims),
            ("group:tu-asset-management-engineers@transurban.com",),
        )

    def test_local_dev_fallback_when_enabled(self) -> None:
        """When ALLOW_LOCAL_DEV_AUTH=true and no IAP header is present, return local dev user."""
        with patch.dict(
            os.environ,
            {
                "ALLOW_LOCAL_DEV_AUTH": "true",
                "LOCAL_DEV_USER_EMAIL": "dev.engineer@transurban.com",
            },
            clear=False,
        ):
            user = resolve_user_from_headers(headers={})
            self.assertEqual(user.email, "dev.engineer@transurban.com")
            self.assertEqual(user.auth_mode, "local_workstation_dev")
            self.assertTrue(check_user_group_access(user, DEFAULT_ALLOWED_GROUPS))

    def test_production_mode_rejects_unauthenticated_requests(self) -> None:
        """When ALLOW_LOCAL_DEV_AUTH=false and no IAP JWT header exists, raise IAPAuthenticationError."""
        with patch.dict(os.environ, {"ALLOW_LOCAL_DEV_AUTH": "false"}, clear=False):
            with self.assertRaises(IAPAuthenticationError):
                resolve_user_from_headers(headers={})


if __name__ == "__main__":
    unittest.main()
