"""Shared redaction for stream addresses in logs and error responses."""
import re
from urllib.parse import urlsplit, urlunsplit


def redact_url_credentials(value):
    text = str(value or "")
    if "://" not in text:
        return text
    try:
        parts = urlsplit(text)
        if "@" not in parts.netloc:
            return text
        return urlunsplit((parts.scheme, "***@" + parts.netloc.rsplit("@", 1)[1],
                           parts.path, parts.query, parts.fragment))
    except ValueError:
        return "<invalid stream URL>"


def redact_stream_text(value):
    return re.sub(r"rtsps?://[^\s\"'<>]+", lambda m: redact_url_credentials(m.group(0)), str(value or ""))
