"""Redaction applied to everything the responder writes or sends.

Telemetry (#56) already keeps cookies, e-mail addresses and request bodies out
of its signals. This is the second layer, for what the responder adds: the
container's stderr, the raw alert payload and the agent's output. Every file in
an incident folder and the prompt pass through `redact`.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

REDACTED = "[redacted]"

#: Header names whose value is never kept, as text or as a JSON key.
HEADER_NAMES = ("set-cookie", "cookie", "authorization", "x-responder-token")

_HEADER = re.compile(
    r"""(?ix)
    ((?:\\?["'])?\b(?:set-cookie|cookie|authorization|x-responder-token)\b(?:\\?["'])?\s*[:=]\s*)
    (
      \\"(?:[^"\\\n]|\\[^"\n])*\\"   # a value quoted inside a JSON string: \"...\"
    | "(?:[^"\\\n]|\\.)*"           # a quoted value
    | '[^'\n]*'
    | [^\n,}"'\\]*                  # unquoted: stops before any quote or backslash
    )
    """
)


def _header_value(match: "re.Match[str]") -> str:
    """Keep the value's own quotes, so a JSON document stays a JSON document."""
    value = match.group(2)
    if value.startswith('\\"'):
        quote = '\\"'
    else:
        quote = value[:1] if value[:1] in ("'", '"') else ""
    return match.group(1) + quote + REDACTED + quote


_RULES = (
    # Header-shaped values, in plain text or JSON: Cookie, Set-Cookie, Authorization.
    (_HEADER, _header_value),
    # A session cookie anywhere else: session=<value>.
    (re.compile(r"(?i)\b(session(?:id|_id)?)=([^;,\s\"']+)"), r"\1=" + REDACTED),
    # Bearer tokens.
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+"), "Bearer " + REDACTED),
    # E-mail addresses.
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}"), "[email]"),
)


def redact(text: str, secrets: Iterable[str] = ()) -> str:
    for secret in secrets:
        if secret:
            text = text.replace(secret, REDACTED)
    for pattern, replacement in _RULES:
        text = pattern.sub(replacement, text)
    return text


def is_header_name(key: str) -> bool:
    return key.strip().lower().replace("_", "-") in HEADER_NAMES


def redact_data(data: Any, secrets: Iterable[str] = ()) -> Any:
    """Redact a JSON-like value before it is serialised: every string through
    `redact`, and the whole value of any key named like a credential header
    (cookie, set-cookie, authorization, x-responder-token; any case) blanked.
    Use this, never `redact` on the serialised text, for anything that becomes
    JSON: inside JSON a quoted value is escaped and text patterns can miss it."""
    secrets = tuple(secrets)
    if isinstance(data, str):
        return redact(data, secrets)
    if isinstance(data, dict):
        clean = {}
        for key, value in data.items():
            name = redact(key, secrets) if isinstance(key, str) else key
            clean[name] = REDACTED if isinstance(key, str) and is_header_name(key) else redact_data(value, secrets)
        return clean
    if isinstance(data, (list, tuple)):
        return [redact_data(v, secrets) for v in data]
    return data


_HOME_PATH = re.compile(r"(?:/Users|/home)/[A-Za-z0-9_.-]+")


def scrub_paths(text: str, replacements: Iterable[tuple]) -> str:
    """For text that leaves the machine (the pull request): named local paths
    become placeholders, and any remaining home-directory path becomes `~`."""
    for path, placeholder in sorted(replacements, key=lambda p: -len(str(p[0]))):
        if path:
            text = text.replace(str(path), placeholder)
    return _HOME_PATH.sub("~", text)
