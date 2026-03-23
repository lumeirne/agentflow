"""Token redaction filter — prevents OAuth tokens from appearing in logs or persisted data."""

import re
from typing import Any


# Keys that should have their values redacted
SENSITIVE_KEYS = {
    "access_token",
    "refresh_token",
    "token",
    "secret",
    "password",
    "authorization",
    "client_secret",
}

# Pattern for detecting token-like strings
TOKEN_PATTERN = re.compile(r'[A-Za-z0-9_\-]{20,}')


def redact_dict(data: dict, depth: int = 0) -> dict:
    """
    Recursively redact sensitive values in a dictionary.
    
    Replaces values for keys matching SENSITIVE_KEYS with '[REDACTED]'.
    """
    if depth > 10:
        return data

    redacted = {}
    for key, value in data.items():
        if key.lower() in SENSITIVE_KEYS:
            redacted[key] = "[REDACTED]"
        elif isinstance(value, dict):
            redacted[key] = redact_dict(value, depth + 1)
        elif isinstance(value, list):
            redacted[key] = [
                redact_dict(item, depth + 1) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            redacted[key] = value

    return redacted


def redact_string(text: str) -> str:
    """Remove token-like strings from a text value."""
    # This is a best-effort filter for catching leaked tokens in error messages
    return TOKEN_PATTERN.sub("[REDACTED]", text)
