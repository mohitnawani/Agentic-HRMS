import re
from typing import Annotated, Any

from pydantic import AfterValidator, BeforeValidator
from pydantic_core import PydanticCustomError

EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)


def normalize_email(value: Any) -> str:
    """Store emails in one canonical form for reliable uniqueness checks."""
    if not isinstance(value, str):
        raise PydanticCustomError("email_type", "Enter a valid email address")
    return value.strip().lower()


def validate_email(value: str) -> str:
    if not 5 <= len(value) <= 254:
        raise ValueError("Enter a valid email address")

    local_part = value.partition("@")[0]
    if (
        len(local_part) > 64
        or local_part.startswith(".")
        or local_part.endswith(".")
        or ".." in local_part
        or EMAIL_PATTERN.fullmatch(value) is None
    ):
        raise ValueError("Enter a valid email address")
    return value


EmailT = Annotated[
    str,
    BeforeValidator(normalize_email),
    AfterValidator(validate_email),
]


def validate_password(value: str) -> str:
    """One password policy for every account entry point (REST + agent chat).

    Minimum 8 characters with at least one letter and one number; capped at
    72 bytes because bcrypt cannot hash more than that.
    """
    if len(value) < 8:
        raise ValueError("Password must be at least 8 characters")
    if len(value.encode("utf-8")) > 72:
        raise ValueError("Password is too long (maximum 72 bytes)")
    if re.search(r"[A-Za-z]", value) is None or re.search(r"[0-9]", value) is None:
        raise ValueError("Password must include at least one letter and one number")
    return value


PasswordT = Annotated[str, AfterValidator(validate_password)]
