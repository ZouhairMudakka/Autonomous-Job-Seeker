"""Remove credentials and personal form contents from diagnostic payloads."""

import re


_SENSITIVE_KEYS = {
    'password', 'passwd', 'secret', 'apikey', 'authorization', 'cookie', 'cookies',
    'accesstoken', 'refreshtoken', 'token', 'credentials', 'email', 'phone',
    'address', 'rawtext', 'cvdata', 'parsedcvdata', 'formdata', 'formvalues',
    'value', 'text', 'resume', 'coverletter',
}
_CREDENTIAL = re.compile(
    r'''(?i)(["']?(?:password|passwd|api[_-]?key|access[_-]?token|refresh[_-]?token|secret)["']?\s*[:=]\s*)(?:"[^"]*"|'[^']*'|[^\s,;&}]+)'''
)
_BEARER = re.compile(r'(?i)\bBearer\s+[^\s,;"\']+')
_EMAIL = re.compile(r'\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b', re.I)


def redact_text(value):
    text = _CREDENTIAL.sub(r'\1[REDACTED]', str(value))
    text = _BEARER.sub('Bearer [REDACTED]', text)
    return _EMAIL.sub('[REDACTED EMAIL]', text)


def redact_data(value):
    """Return a sanitized copy; never mutate data used by the application."""
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            normalized = re.sub(r'[^a-z0-9]', '', str(key).lower())
            sensitive = normalized in _SENSITIVE_KEYS or any(
                normalized.endswith(suffix) for suffix in ('password', 'secret', 'apikey', 'accesstoken', 'refreshtoken')
            )
            if normalized == 'value' and isinstance(item, (int, float, bool)):
                sensitive = False  # Numeric metric values contain no form text.
            result[str(key)] = '[REDACTED]' if sensitive else redact_data(item)
        return result
    if isinstance(value, (list, tuple)):
        return [redact_data(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value
