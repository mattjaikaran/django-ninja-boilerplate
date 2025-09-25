"""Core application constants.

This module contains all the constants used across the application
to ensure consistency and maintainability.
"""

# API Configuration
API_VERSION = "v1"
API_PREFIX = f"/api/{API_VERSION}"

# Pagination Settings
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# Cache Configuration
CACHE_KEY_PREFIX = "boilerplate_api"
CACHE_TIMEOUT_SHORT = 300  # 5 minutes
CACHE_TIMEOUT_MEDIUM = 1800  # 30 minutes
CACHE_TIMEOUT_LONG = 3600  # 1 hour
CACHE_TIMEOUT_DAY = 86400  # 24 hours

# Redis Key Patterns
REDIS_KEYS = {
    "user_sessions": f"{CACHE_KEY_PREFIX}:user_sessions",
    "todo_cache": f"{CACHE_KEY_PREFIX}:todos",
    "user_cache": f"{CACHE_KEY_PREFIX}:users",
}

# File Upload Settings
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"]
ALLOWED_DOCUMENT_EXTENSIONS = [".pdf", ".doc", ".docx", ".txt", ".csv", ".xlsx"]

# Email Template Paths
EMAIL_TEMPLATES = {
    "welcome": "emails/welcome.html",
    "password_reset": "emails/password_reset.html",
    "todo_reminder": "emails/todo_reminder.html",
}

# User Account Settings
USERNAME_MAX_LENGTH = 150
PHONE_NUMBER_MAX_LENGTH = 20
PASSWORD_MIN_LENGTH = 8

# Security Settings
SESSION_TIMEOUT = 1800  # 30 minutes
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION = 900  # 15 minutes
OTP_EXPIRY_MINUTES = 10
JWT_EXPIRY_HOURS = 24

# Logging Configuration
LOG_LEVELS = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}

# Health Check Services
HEALTH_CHECK_SERVICES = [
    "database",
    "redis",
]

# Rate Limiting
RATE_LIMIT_PER_MINUTE = 60
RATE_LIMIT_PER_HOUR = 1000
RATE_LIMIT_PER_DAY = 10000
RATE_LIMIT_BURST = 10

# Search Configuration
SEARCH_RESULTS_PER_PAGE = 20
MAX_SEARCH_RESULTS = 1000
SEARCH_TIMEOUT = 5  # seconds
MIN_SEARCH_QUERY_LENGTH = 2

# Feature Flags
FEATURES = {
    "ENABLE_TODO_REMINDERS": True,
    "ENABLE_USER_PROFILES": True,
    "ENABLE_NOTIFICATIONS": False,
}

# Date/Time Formats
DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
TIME_FORMAT = "%H:%M:%S"
