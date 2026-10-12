"""Chat/messaging feature generator."""

from .base_generator import BaseGenerator, GeneratorError
from .templates.chat_templates import render_chat_files


class ChatGenerator(BaseGenerator):
    """Generator for the chat/messaging feature.

    The app gets conversation and message controllers behind ``JWTAuth``,
    services that scope every query to the user's conversations, and one
    smoke and permission test file.
    """

    def __init__(
        self,
        app_name: str = "chat",
        minimal: bool = False,
        realtime: bool = False,
    ):
        """Initialize the chat generator.

        Args:
            app_name: Name of the Django app to create
            minimal: Whether to generate minimal version
            realtime: Whether to add the Centrifugo real-time service
        """
        super().__init__(app_name, minimal)
        self.realtime = realtime

    def generate(self) -> None:
        """Generate the chat feature."""
        if self.app_path.exists():
            msg = f"App '{self.app_name}' already exists"
            raise GeneratorError(msg)

        self.logger.info("Generating chat feature in %s...", self.app_name)
        self.create_django_app()
        self.remove_scaffold()
        for relative_path, content in render_chat_files(self.app_name).items():
            self.create_file(self.app_path / relative_path, content)
        if self.realtime:
            self._generate_realtime_service()

        # The schemas and ConversationService read these settings.
        self.update_settings(
            self.app_name,
            {
                "CHAT_MESSAGE_MAX_LENGTH": 2000,
                "CHAT_CONVERSATION_MAX_PARTICIPANTS": 100,
            },
        )
        self.update_urls(self.app_name, "ConversationController", "MessageController")
        self.create_migration()
        self.logger.info(
            "Chat feature generated at /api/conversations/ and /api/messages/"
        )

    def _generate_realtime_service(self) -> None:
        """Generate the Centrifugo real-time service for chat."""
        from .templates.chat_templates import CHAT_REALTIME_SERVICE_TEMPLATE

        self.create_file(
            self.app_path / "services" / "realtime_service.py",
            CHAT_REALTIME_SERVICE_TEMPLATE.format(app_name=self.app_name),
        )
