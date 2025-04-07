import re

from wtforms import (
    ValidationError,
)
from wtforms.validators import DataRequired, Email, Length, Regexp

gmail_validators = [
    DataRequired(),
    Email(),
    Length(min=6, max=100),
    Regexp(
        r"^[A-Za-z0-9_.+-]+@gmail\.com$",
        flags=0,
        message="Email must be a Gmail address.",
    ),
]


def strip_filter(value):
    return value.strip() if value else value


def validate_username(_, field):
    username = field.data or ""

    if not username[0].isalpha():
        raise ValidationError("Username must start with a letter.")

    if username[-1] in "._":
        raise ValidationError("Username must end with a letter or digit.")

    for char in username:
        if char.isalpha() and not char.islower():
            raise ValidationError("Username must use only lowercase letters.")
        if not (char.isdigit() or char.islower() or char in "._"):
            raise ValidationError(
                "Username may only contain lowercase letters, digits, '.' or '_'."
            )


def validate_phone(form, field):
    if field.data:
        pattern = re.compile(r"^\+?[\d\s\-\(\)]+$")
        if not pattern.match(field.data):
            raise ValidationError("Invalid phone number format.")


def calculate_word_count(_, field):
    if field.data:
        word_count = len(field.data.split())
        if word_count > 300:
            raise ValidationError("Message cannot be more than 300 words.")
