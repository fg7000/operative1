"""
Media validation service for Operative1.

Validates uploaded media against platform requirements:
- File type (magic bytes + extension)
- File size
- Dimensions (future)

Platform limits (images only for MVP):
- Twitter: JPEG, PNG, GIF, WebP. Max 5MB static, 15MB GIF
- Reddit: JPEG, PNG, GIF. Max 20MB
- LinkedIn: JPEG, PNG. Max 5MB
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Magic bytes for common image formats
MAGIC_BYTES = {
    b'\xff\xd8\xff': 'image/jpeg',
    b'\x89PNG\r\n\x1a\n': 'image/png',
    b'GIF87a': 'image/gif',
    b'GIF89a': 'image/gif',
    b'RIFF': 'image/webp',  # WebP starts with RIFF, need to check for WEBP after
}

# Extension to MIME type mapping
EXTENSION_TO_MIME = {
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'png': 'image/png',
    'gif': 'image/gif',
    'webp': 'image/webp',
}

# Platform-specific limits
PLATFORM_LIMITS = {
    'twitter': {
        'allowed_types': ['image/jpeg', 'image/png', 'image/gif', 'image/webp'],
        'max_size_bytes': 5 * 1024 * 1024,  # 5MB for static images
        'max_size_gif_bytes': 15 * 1024 * 1024,  # 15MB for GIFs
    },
    'reddit': {
        'allowed_types': ['image/jpeg', 'image/png', 'image/gif'],
        'max_size_bytes': 20 * 1024 * 1024,  # 20MB
    },
    'linkedin': {
        'allowed_types': ['image/jpeg', 'image/png'],
        'max_size_bytes': 5 * 1024 * 1024,  # 5MB
    },
    'hn': {
        'allowed_types': [],  # HN doesn't support images
        'max_size_bytes': 0,
    },
}


def get_magic_bytes_type(content: bytes) -> Optional[str]:
    """Detect file type from magic bytes (first bytes of file)."""
    if len(content) < 8:
        return None

    # Check each magic byte pattern
    for magic, mime in MAGIC_BYTES.items():
        if content[:len(magic)] == magic:
            # Special handling for WebP (RIFF + WEBP)
            if magic == b'RIFF' and len(content) >= 12:
                if content[8:12] == b'WEBP':
                    return 'image/webp'
                else:
                    return None  # RIFF but not WebP
            return mime

    return None


def validate_extension_matches_mime(extension: str, mime_type: str) -> bool:
    """Validate that file extension matches detected MIME type."""
    expected_mime = EXTENSION_TO_MIME.get(extension.lower())
    return expected_mime == mime_type


def validate_media(
    content: bytes,
    detected_type: str,
    extension: str,
    platform: str
) -> dict:
    """
    Validate media against platform requirements.

    Args:
        content: File content bytes
        detected_type: MIME type detected from magic bytes
        extension: File extension
        platform: Target platform

    Returns:
        {
            'valid': bool,
            'error': str or None,
            'detected_type': str,
            'size_bytes': int,
        }
    """
    size_bytes = len(content)

    # Check extension matches detected type
    if not validate_extension_matches_mime(extension, detected_type):
        return {
            'valid': False,
            'error': f"File extension '.{extension}' does not match detected type '{detected_type}'",
            'detected_type': detected_type,
            'size_bytes': size_bytes,
        }

    # Get platform limits
    limits = PLATFORM_LIMITS.get(platform)
    if not limits:
        return {
            'valid': False,
            'error': f"Unknown platform: {platform}",
            'detected_type': detected_type,
            'size_bytes': size_bytes,
        }

    # Check if type is allowed
    if detected_type not in limits['allowed_types']:
        allowed = ', '.join(limits['allowed_types']) or 'none'
        return {
            'valid': False,
            'error': f"{platform.title()} does not support {detected_type}. Allowed: {allowed}",
            'detected_type': detected_type,
            'size_bytes': size_bytes,
        }

    # Check size
    max_size = limits['max_size_bytes']
    if detected_type == 'image/gif' and 'max_size_gif_bytes' in limits:
        max_size = limits['max_size_gif_bytes']

    if size_bytes > max_size:
        max_mb = max_size / (1024 * 1024)
        actual_mb = size_bytes / (1024 * 1024)
        return {
            'valid': False,
            'error': f"File is {actual_mb:.1f}MB. {platform.title()} allows max {max_mb:.0f}MB for {detected_type}.",
            'detected_type': detected_type,
            'size_bytes': size_bytes,
        }

    return {
        'valid': True,
        'error': None,
        'detected_type': detected_type,
        'size_bytes': size_bytes,
    }
