import re

from aggregator.errors import InvalidInput, ReservedProviderName

PROVIDER_RE = re.compile(r"^[a-z][a-z0-9-]{1,31}$")
USER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
RESERVED_NAMES = {
    "providers",
    "requests",
    "callback",
    "healthz",
    "readyz",
    "metrics",
    "docs",
    "redoc",
}
PROVIDER_TYPES = {"github", "gitlab", "google", "oidc", "custom"}
DEFAULT_SCOPES = {
    "github": ["read:user"],
    "gitlab": ["read_user"],
    "google": ["openid", "email", "profile"],
    "oidc": ["openid"],
    "custom": ["openid"],
}
SCOPE_RE = re.compile(r"^[\x21\x23-\x5B\x5D-\x7E]+$")


def provider_name(value: str) -> str:
    if not PROVIDER_RE.fullmatch(value):
        raise InvalidInput("Provider name must use lowercase letters, digits, and hyphens.")
    if value in RESERVED_NAMES:
        raise ReservedProviderName()
    return value


def user_id(value: str) -> str:
    if not USER_RE.fullmatch(value):
        raise InvalidInput("User ID contains unsupported characters.")
    return value


def scopes_valid(values: list[str]) -> bool:
    return len(values) <= 20 and all(SCOPE_RE.fullmatch(item) for item in values)


def creds_name(provider: str, user: str) -> str:
    return f"{provider_name(provider)}_{user_id(user)}"
