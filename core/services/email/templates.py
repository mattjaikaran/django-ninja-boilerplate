"""Email template handling and data structures."""

from typing import Any, Protocol

from django.template.loader import render_to_string


class EmailTemplateData(Protocol):
    """Protocol for email template data structure."""

    subject_template: str | None
    html_template: str | None
    text_template: str | None
    context: dict[str, Any]


class EmailTemplateRenderer:
    """Handles rendering of email templates."""

    @staticmethod
    def render_subject(template_data: EmailTemplateData) -> str:
        """Render email subject from template or use default."""
        if template_data.subject_template:
            return render_to_string(
                template_data.subject_template, template_data.context
            ).strip()
        return template_data.context.get("subject", "No Subject")

    @staticmethod
    def render_html_template(template_data: EmailTemplateData) -> str | None:
        """Render HTML template if provided."""
        if template_data.html_template:
            return render_to_string(template_data.html_template, template_data.context)
        return None

    @staticmethod
    def render_text_template(template_data: EmailTemplateData) -> str | None:
        """Render text template if provided."""
        if template_data.text_template:
            return render_to_string(template_data.text_template, template_data.context)
        return None


def dict_to_template_data(data: dict[str, Any]) -> EmailTemplateData:
    """Convert dictionary to EmailTemplateData object."""

    class TemplateData:
        def __init__(self, data: dict[str, Any]):
            self.subject_template = data.get("subject_template")
            self.html_template = data.get("html_template")
            self.text_template = data.get("text_template")
            self.context = data.get("context", {})

    return TemplateData(data)
