"""
Unit tests for PasswordGenerator with alphanumeric_only support
"""

import pytest
import string
from src.security_utils import PasswordGenerator


class TestPasswordGenerator:
    """Test password generation with alphanumeric_only option"""

    def test_generate_app_password_with_special_chars(self):
        """Test password generation with special characters (default)"""
        password = PasswordGenerator.generate_app_password("test_app", alphanumeric_only=False)

        assert len(password) == 64
        assert any(c.isupper() for c in password), "Should have uppercase"
        assert any(c.islower() for c in password), "Should have lowercase"
        assert any(c.isdigit() for c in password), "Should have digits"
        assert any(c in "@_!#%&*-+=" for c in password), "Should have special chars"

    def test_generate_app_password_alphanumeric_only(self):
        """Test password generation without special characters"""
        password = PasswordGenerator.generate_app_password("portainer", alphanumeric_only=True)

        assert len(password) == 64
        assert password.isalnum(), "Should only contain alphanumeric characters"
        assert any(c.isupper() for c in password), "Should have uppercase"
        assert any(c.islower() for c in password), "Should have lowercase"
        assert any(c.isdigit() for c in password), "Should have digits"
        assert not any(c in string.punctuation for c in password), "Should NOT have special chars"

    def test_multiple_alphanumeric_passwords_are_different(self):
        """Test that multiple generated alphanumeric passwords are unique"""
        passwords = [
            PasswordGenerator.generate_app_password(f"app_{i}", alphanumeric_only=True)
            for i in range(10)
        ]

        # All should be unique
        assert len(set(passwords)) == 10, "All passwords should be unique"

        # All should be alphanumeric
        for password in passwords:
            assert password.isalnum()
            assert len(password) == 64

    def test_password_strength_alphanumeric(self):
        """Test that alphanumeric passwords are still strong"""
        password = PasswordGenerator.generate_app_password("test", alphanumeric_only=True)

        # 64 characters of alphanumeric (62 possible chars) gives huge entropy
        # log2(62^64) ≈ 380 bits of entropy
        assert len(password) == 64

        # Should have good character distribution
        uppercase_count = sum(1 for c in password if c.isupper())
        lowercase_count = sum(1 for c in password if c.islower())
        digit_count = sum(1 for c in password if c.isdigit())

        # Each type should appear at least once (enforced by generator)
        assert uppercase_count >= 1
        assert lowercase_count >= 1
        assert digit_count >= 1

        # Roughly even distribution (with some variance allowed)
        assert uppercase_count >= 10, "Should have reasonable uppercase distribution"
        assert lowercase_count >= 10, "Should have reasonable lowercase distribution"
        assert digit_count >= 5, "Should have reasonable digit distribution"

    def test_portainer_password_compatibility(self):
        """Test that Portainer passwords are safe for Docker/shell"""
        password = PasswordGenerator.generate_app_password("portainer", alphanumeric_only=True)

        # No characters that need escaping in shell or Docker
        dangerous_chars = ["$", "'", '"', "`", "\\", "!", "&", "|", ";", "(", ")",
                          "{", "}", "[", "]", "<", ">", "*", "?", "~", "#"]

        for char in dangerous_chars:
            assert char not in password, f"Password should not contain '{char}'"

        # Should be safe to use in:
        # - Docker environment variables
        # - Shell commands without quotes
        # - JSON/YAML without escaping
        assert password.isalnum()

    def test_postgres_redis_password_compatibility(self):
        """Test that database passwords are compatible"""
        postgres_pass = PasswordGenerator.generate_app_password("postgres", alphanumeric_only=True)
        redis_pass = PasswordGenerator.generate_app_password("redis", alphanumeric_only=True)

        # Both should be alphanumeric for compatibility
        assert postgres_pass.isalnum()
        assert redis_pass.isalnum()

        # Should be different
        assert postgres_pass != redis_pass

        # Should work in connection strings without encoding
        # postgres://user:password@host:port/db
        # redis://:password@host:port
        for char in postgres_pass + redis_pass:
            assert char not in ":/@?#[]", "Should not contain URL special chars"