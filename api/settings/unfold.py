"""Django Unfold admin configuration.

Separated from common.py to keep settings manageable.
"""

UNFOLD = {
    "SITE_TITLE": "Django Ninja Admin",
    "SITE_HEADER": "Django Ninja Boilerplate",
    "SITE_SYMBOL": "speed",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": False,
    "DASHBOARD_CALLBACK": "core.admin.dashboard.dashboard_callback",
    "STYLES": [],
    "SCRIPTS": [],
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": True,
        "navigation": [
            {
                "title": "Core",
                "items": [
                    {"title": "Users", "icon": "person", "link": "/admin/auth/user/"},
                    {"title": "API Keys", "icon": "key", "link": "/admin/core/apikey/"},
                    {
                        "title": "Audit Log",
                        "icon": "history",
                        "link": "/admin/core/auditlog/",
                    },
                ],
            },
            {
                "title": "Monitoring",
                "items": [
                    {
                        "title": "Health Check",
                        "icon": "monitor_heart",
                        "link": "/api/health/detailed",
                    },
                    {"title": "Metrics", "icon": "bar_chart", "link": "/api/metrics"},
                    {
                        "title": "Flower (Celery)",
                        "icon": "local_shipping",
                        "link": "http://localhost:5555",
                    },
                ],
            },
        ],
    },
    "TABS": [],
}
