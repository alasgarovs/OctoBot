"""Phone number cleaning. No Qt imports here."""

import math

_FORMAT_CHARS = str.maketrans("", "", "+-() \t\n\r ")

# E.164: at most 15 digits. Anything shorter than 7 is not a real number.
MIN_DIGITS = 7
MAX_DIGITS = 15


def clean_number(value):
    """Excel cell -> digits-only phone number as a string, or None if invalid."""
    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, float):
        if math.isnan(value) or not value.is_integer():
            return None
        text = str(int(value))
    elif isinstance(value, int):
        text = str(value)
    else:
        text = str(value).strip()
        if text.endswith(".0"):
            text = text[:-2]
        text = text.translate(_FORMAT_CHARS)

    if not text.isascii() or not text.isdigit():
        return None
    if not (MIN_DIGITS <= len(text) <= MAX_DIGITS):
        return None

    return text
