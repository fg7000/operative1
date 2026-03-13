"""
Encryption service for Operative1 API.

Uses Fernet symmetric encryption for storing sensitive credentials.
Encryption key is stored in ENCRYPTION_KEY environment variable.

Usage:
    from services.encryption import encrypt_credentials, decrypt_credentials

    encrypted = encrypt_credentials(auth_token, ct0)
    decrypted = decrypt_credentials(encrypted)  # Returns dict or None
"""

import os
import json
import logging
from typing import Optional
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

# Get encryption key from environment
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY')

_fernet: Optional[Fernet] = None


def _get_fernet() -> Optional[Fernet]:
    """Get or create Fernet instance."""
    global _fernet
    if _fernet is not None:
        return _fernet

    if not ENCRYPTION_KEY:
        logger.warning("ENCRYPTION_KEY not configured - credentials will not be encrypted")
        return None

    try:
        _fernet = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)
        return _fernet
    except Exception as e:
        logger.error(f"Failed to initialize Fernet with ENCRYPTION_KEY: {e}")
        return None


def encrypt_credentials(auth_token: str, ct0: str) -> str:
    """
    Encrypt Twitter credentials for storage.

    Returns encrypted string, or JSON string if encryption unavailable.
    """
    data = json.dumps({'auth_token': auth_token, 'ct0': ct0})

    fernet = _get_fernet()
    if fernet:
        try:
            encrypted = fernet.encrypt(data.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            # Fall through to unencrypted storage

    # Fallback: store unencrypted (not recommended for production)
    logger.warning("Storing credentials unencrypted - set ENCRYPTION_KEY")
    return data


def decrypt_credentials(encrypted: str) -> Optional[dict]:
    """
    Decrypt Twitter credentials from storage.

    Returns dict with 'auth_token' and 'ct0', or None if decryption fails.
    """
    if not encrypted:
        return None

    fernet = _get_fernet()

    # Try decryption first
    if fernet:
        try:
            decrypted = fernet.decrypt(encrypted.encode())
            return json.loads(decrypted.decode())
        except InvalidToken:
            # Token is invalid - might be unencrypted JSON
            pass
        except Exception as e:
            logger.error(f"Decryption failed: {e}")

    # Try parsing as plain JSON (legacy unencrypted data)
    try:
        data = json.loads(encrypted)
        if isinstance(data, dict) and 'auth_token' in data and 'ct0' in data:
            return data
    except json.JSONDecodeError:
        pass

    logger.error("Failed to decrypt credentials")
    return None


def is_encryption_configured() -> bool:
    """Check if encryption is properly configured."""
    return _get_fernet() is not None
