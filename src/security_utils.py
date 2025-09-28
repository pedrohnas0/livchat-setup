"""
Security utilities for password generation and credentials management
"""
import secrets
import string
import logging
from typing import Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AppCredentials:
    """Credentials for an application"""
    app_name: str
    email: str
    username: str
    password: str
    url: Optional[str] = None
    additional_info: Dict = None


class PasswordGenerator:
    """Generate secure passwords for applications"""

    @staticmethod
    def generate_secure_password(length: int = 64,
                                include_uppercase: bool = True,
                                include_lowercase: bool = True,
                                include_digits: bool = True,
                                include_special: bool = True,
                                special_chars: str = "@_!#$%^&*()-+=[]{}|:;<>,.?/~") -> str:
        """
        Generate a secure random password

        Args:
            length: Password length (default: 64)
            include_uppercase: Include uppercase letters
            include_lowercase: Include lowercase letters
            include_digits: Include digits
            include_special: Include special characters
            special_chars: Special characters to use

        Returns:
            Generated password
        """
        # Build character pool
        characters = ""

        if include_lowercase:
            characters += string.ascii_lowercase
        if include_uppercase:
            characters += string.ascii_uppercase
        if include_digits:
            characters += string.digits
        if include_special:
            characters += special_chars

        if not characters:
            raise ValueError("At least one character type must be included")

        # Generate password
        password = ''.join(secrets.choice(characters) for _ in range(length))

        # Ensure at least one of each required type is present
        required = []
        if include_lowercase and not any(c.islower() for c in password):
            required.append(secrets.choice(string.ascii_lowercase))
        if include_uppercase and not any(c.isupper() for c in password):
            required.append(secrets.choice(string.ascii_uppercase))
        if include_digits and not any(c.isdigit() for c in password):
            required.append(secrets.choice(string.digits))
        if include_special and not any(c in special_chars for c in password):
            required.append(secrets.choice(special_chars))

        # If we had to add required characters, replace some random positions
        if required:
            password_list = list(password)
            for char in required:
                pos = secrets.randbelow(len(password_list))
                password_list[pos] = char
            password = ''.join(password_list)

        logger.info(f"Generated secure password with {length} characters")
        return password

    @staticmethod
    def generate_app_password(app_name: str = "default", alphanumeric_only: bool = False) -> str:
        """
        Generate a 64-character secure password for applications

        Args:
            app_name: Name of the application
            alphanumeric_only: If True, only use letters and numbers (no special chars)

        Returns:
            64-character secure password
        """
        if alphanumeric_only:
            # Generate alphanumeric-only password for apps that don't handle special chars well
            password = PasswordGenerator.generate_secure_password(
                length=64,
                include_uppercase=True,
                include_lowercase=True,
                include_digits=True,
                include_special=False  # No special characters
            )
            logger.info(f"Generated 64-character alphanumeric password for {app_name}")
        else:
            # Use safe special characters that work well with most applications
            safe_special_chars = "@_!#%&*-+="
            password = PasswordGenerator.generate_secure_password(
                length=64,
                include_uppercase=True,
                include_lowercase=True,
                include_digits=True,
                include_special=True,
                special_chars=safe_special_chars
            )
            logger.info(f"Generated 64-character password with special chars for {app_name}")

        return password

    @staticmethod
    def validate_password(password: str,
                         min_length: int = 12,
                         require_uppercase: bool = True,
                         require_lowercase: bool = True,
                         require_digits: bool = True,
                         require_special: bool = True) -> tuple[bool, str]:
        """
        Validate password strength

        Args:
            password: Password to validate
            min_length: Minimum length required
            require_uppercase: Require uppercase letters
            require_lowercase: Require lowercase letters
            require_digits: Require digits
            require_special: Require special characters

        Returns:
            Tuple of (is_valid, error_message)
        """
        if len(password) < min_length:
            return False, f"Password must be at least {min_length} characters"

        if require_uppercase and not any(c.isupper() for c in password):
            return False, "Password must contain at least one uppercase letter"

        if require_lowercase and not any(c.islower() for c in password):
            return False, "Password must contain at least one lowercase letter"

        if require_digits and not any(c.isdigit() for c in password):
            return False, "Password must contain at least one digit"

        if require_special and not any(c in string.punctuation for c in password):
            return False, "Password must contain at least one special character"

        return True, "Password is valid"


class CredentialsManager:
    """Manage application credentials with Vault integration"""

    def __init__(self, storage_manager):
        """
        Initialize CredentialsManager

        Args:
            storage_manager: StorageManager instance for Vault access
        """
        self.storage = storage_manager
        self.password_gen = PasswordGenerator()
        # Default email for all applications - should be configured by user
        self.default_email = None

    def generate_app_credentials(self, app_name: str,
                                email: str = None,
                                username: str = None,
                                custom_password: str = None,
                                url: str = None,
                                alphanumeric_only: bool = False) -> AppCredentials:
        """
        Generate credentials for an application

        Args:
            app_name: Name of the application
            email: Email address (uses default if not provided)
            username: Username (default: admin)
            custom_password: Use custom password instead of generating
            url: Application URL
            alphanumeric_only: If True, generate password without special chars

        Returns:
            AppCredentials object
        """
        # Email is required - either provided or from config
        if not email:
            # Try to get from config
            email_config = self.storage.config.get("admin_email")
            if not email_config:
                raise ValueError("Email is required. Please provide email or set 'admin_email' in config")
            email = email_config

        # For Portainer and similar apps, use email as username by default
        if not username:
            username = email if app_name in ["portainer", "grafana", "nextcloud"] else "admin"

        # Generate or use provided password
        if custom_password:
            # Validate custom password
            is_valid, error_msg = self.password_gen.validate_password(custom_password)
            if not is_valid:
                logger.warning(f"Custom password validation failed: {error_msg}")
                # Still use it if explicitly provided
            password = custom_password
        else:
            # Generate secure 64-character password
            # Use alphanumeric only for apps that have issues with special chars
            password = self.password_gen.generate_app_password(app_name, alphanumeric_only=alphanumeric_only)

        credentials = AppCredentials(
            app_name=app_name,
            email=email,
            username=username,
            password=password,
            url=url
        )

        logger.info(f"Generated credentials for {app_name} with email {email}")
        return credentials

    def save_credentials(self, credentials: AppCredentials) -> bool:
        """
        Save credentials to Vault

        Args:
            credentials: AppCredentials to save

        Returns:
            Success status
        """
        try:
            # Save to vault with app-specific key
            vault_key = f"{credentials.app_name}_credentials"

            cred_dict = {
                "email": credentials.email,
                "username": credentials.username,
                "password": credentials.password,
                "url": credentials.url
            }

            if credentials.additional_info:
                cred_dict.update(credentials.additional_info)

            self.storage.secrets.set_secret(vault_key, cred_dict)

            logger.info(f"Saved credentials for {credentials.app_name} to Vault")
            return True

        except Exception as e:
            logger.error(f"Failed to save credentials: {e}")
            return False

    def get_credentials(self, app_name: str) -> Optional[AppCredentials]:
        """
        Get credentials from Vault

        Args:
            app_name: Name of the application

        Returns:
            AppCredentials or None if not found
        """
        try:
            vault_key = f"{app_name}_credentials"
            cred_dict = self.storage.secrets.get_secret(vault_key)

            if not cred_dict:
                logger.warning(f"No credentials found for {app_name}")
                return None

            # Handle both string (old format) and dict (new format)
            if isinstance(cred_dict, str):
                # Legacy format - just password
                return AppCredentials(
                    app_name=app_name,
                    email=self.storage.config.get("admin_email", "admin@localhost"),
                    username="admin",
                    password=cred_dict,
                    url=None
                )
            else:
                # New format - full credentials
                return AppCredentials(
                    app_name=app_name,
                    email=cred_dict.get("email", self.storage.config.get("admin_email", "admin@localhost")),
                    username=cred_dict.get("username", "admin"),
                    password=cred_dict.get("password", ""),
                    url=cred_dict.get("url"),
                    additional_info={k: v for k, v in cred_dict.items()
                                   if k not in ["email", "username", "password", "url"]}
                )

        except Exception as e:
            logger.error(f"Failed to get credentials for {app_name}: {e}")
            return None

    def list_credentials(self) -> Dict[str, AppCredentials]:
        """
        List all stored credentials

        Returns:
            Dictionary of app_name -> AppCredentials
        """
        all_secrets = self.storage.secrets.list_secrets()
        credentials = {}

        for key in all_secrets:
            if key.endswith("_credentials"):
                app_name = key.replace("_credentials", "")
                creds = self.get_credentials(app_name)
                if creds:
                    credentials[app_name] = creds

        return credentials