"""Security tests for URL validation in authentication."""

from urllib.parse import urlparse

import pytest


class TestURLValidationSecurity:
    """Test URL validation against bypass attempts."""

    @pytest.mark.parametrize(
        "malicious_url",
        [
            "http://evil.com/melcloudhome.com",
            "http://melcloudhome.com.evil.com",
            "http://evil.com?redirect=melcloudhome.com",
            "http://evilmelcloudhome.com",
            "http://melcloudhome.com@evil.com",
            "http://evil.com#melcloudhome.com",
        ],
    )
    def test_malicious_melcloud_urls_rejected(self, malicious_url):
        """Test that malicious URLs with melcloudhome.com substring are rejected."""
        # Test the URL parsing logic used in auth.py
        parsed = urlparse(malicious_url)
        is_valid = parsed.hostname and (
            parsed.hostname == "melcloudhome.com"
            or parsed.hostname.endswith(".melcloudhome.com")
        )
        assert not is_valid, f"Malicious URL should be rejected: {malicious_url}"

    @pytest.mark.parametrize(
        "legitimate_url",
        [
            "https://melcloudhome.com/dashboard",
            "https://auth.melcloudhome.com/signin",
            "https://api.melcloudhome.com/data",
            "https://www.melcloudhome.com/",
        ],
    )
    def test_legitimate_melcloud_urls_accepted(self, legitimate_url):
        """Test that legitimate melcloudhome.com URLs are accepted."""
        parsed = urlparse(legitimate_url)
        is_valid = parsed.hostname and (
            parsed.hostname == "melcloudhome.com"
            or parsed.hostname.endswith(".melcloudhome.com")
        )
        assert is_valid, f"Legitimate URL should be accepted: {legitimate_url}"

    @pytest.mark.parametrize(
        "malicious_url",
        [
            "http://evil.com/amazoncognito.com/login",
            "http://amazoncognito.com.evil.com/login",
            "http://fake-amazoncognito.com/login",
            "http://amazoncognito.com@evil.com/login",
            "http://evil.com?redirect=amazoncognito.com/login",
        ],
    )
    def test_malicious_cognito_urls_rejected(self, malicious_url):
        """Test that malicious URLs with amazoncognito.com substring are rejected."""
        parsed = urlparse(malicious_url)
        is_valid = parsed.hostname and parsed.hostname.endswith(".amazoncognito.com")
        assert not is_valid, f"Malicious URL should be rejected: {malicious_url}"

    @pytest.mark.parametrize(
        "legitimate_url",
        [
            "https://live-melcloudhome.auth.eu-west-1.amazoncognito.com/login",
            "https://test.auth.us-east-1.amazoncognito.com/login",
            "https://prod.auth.ap-southeast-1.amazoncognito.com/oauth2/authorize",
        ],
    )
    def test_legitimate_cognito_urls_accepted(self, legitimate_url):
        """Test that legitimate amazoncognito.com URLs are accepted."""
        parsed = urlparse(legitimate_url)
        is_valid = parsed.hostname and parsed.hostname.endswith(".amazoncognito.com")
        assert is_valid, f"Legitimate URL should be accepted: {legitimate_url}"

    @pytest.mark.parametrize(
        "cookie_domain,expected_valid",
        [
            (".melcloudhome.com", True),
            ("melcloudhome.com", True),
            ("auth.melcloudhome.com", True),
            ("api.melcloudhome.com", True),
            (".evil.com", False),
            ("evil-melcloudhome.com", False),
            ("melcloudhome.com.evil.com", False),
        ],
    )
    def test_cookie_domain_filtering(self, cookie_domain, expected_valid):
        """Test cookie domain filtering logic used in auth.py."""
        # Test the logic used in auth.py line 131-133
        is_valid = (
            cookie_domain == "melcloudhome.com"
            or cookie_domain == ".melcloudhome.com"
            or cookie_domain.endswith(".melcloudhome.com")
        )
        assert (
            is_valid == expected_valid
        ), f"Cookie domain {cookie_domain} validation mismatch"

    def test_cognito_login_path_validation(self):
        """Test that Cognito URL validation checks both hostname and path."""
        # Valid: Correct hostname and has /login in path
        valid_url = "https://live-melcloudhome.auth.eu-west-1.amazoncognito.com/login?client_id=test"
        parsed = urlparse(valid_url)
        is_valid = (
            parsed.hostname
            and parsed.hostname.endswith(".amazoncognito.com")
            and "/login" in parsed.path
        )
        assert is_valid, "Valid Cognito login URL should be accepted"

        # Invalid: Correct hostname but no /login in path
        invalid_url = "https://live-melcloudhome.auth.eu-west-1.amazoncognito.com/oauth2/authorize"
        parsed = urlparse(invalid_url)
        is_valid = (
            parsed.hostname
            and parsed.hostname.endswith(".amazoncognito.com")
            and "/login" in parsed.path
        )
        assert not is_valid, "Cognito URL without /login path should be rejected"

        # Invalid: Has /login but wrong hostname
        invalid_url2 = "https://evil.com/login"
        parsed = urlparse(invalid_url2)
        is_valid = (
            parsed.hostname
            and parsed.hostname.endswith(".amazoncognito.com")
            and "/login" in parsed.path
        )
        assert not is_valid, "URL with /login but wrong hostname should be rejected"
