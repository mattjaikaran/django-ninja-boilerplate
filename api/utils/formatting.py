"""Text formatting utilities."""

import re


def create_slug(text: str) -> str:
    """Create a URL-friendly slug from text.

    Args:
        text: Text to convert to slug

    Returns:
        URL-friendly slug
    """
    # Convert to lowercase and replace spaces with hyphens
    slug = text.lower().strip()
    # Remove special characters except hyphens and underscores
    slug = re.sub(r"[^\w\s-]", "", slug)
    # Replace multiple spaces/hyphens with single hyphen
    slug = re.sub(r"[-\s]+", "-", slug)
    # Remove leading/trailing hyphens
    slug = slug.strip("-")
    return slug


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to specified length with suffix.

    Args:
        text: Text to truncate
        max_length: Maximum length of text
        suffix: Suffix to add to truncated text

    Returns:
        Truncated text with suffix if needed
    """
    if len(text) <= max_length:
        return text

    # Find the last space before max_length to avoid cutting words
    truncate_at = max_length - len(suffix)
    last_space = text.rfind(" ", 0, truncate_at)

    if last_space > 0:
        return text[:last_space] + suffix
    return text[:truncate_at] + suffix


def format_phone_number(phone: str, country_code: str = "+1") -> str:
    """Format a phone number with country code.

    Args:
        phone: Phone number to format
        country_code: Country code to prepend

    Returns:
        Formatted phone number
    """
    # Remove all non-digit characters
    digits = re.sub(r"\D", "", phone)

    # Add country code if not present
    if not digits.startswith(country_code.replace("+", "")):
        digits = country_code.replace("+", "") + digits

    return f"+{digits}"


def sanitize_string(text: str) -> str:
    """Sanitize string by removing harmful characters.

    Args:
        text: Text to sanitize

    Returns:
        Sanitized text
    """
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Remove script tags and their content
    text = re.sub(r"<script.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    # Remove potentially harmful characters
    text = re.sub(r'[<>"\']', "", text)
    return text.strip()
