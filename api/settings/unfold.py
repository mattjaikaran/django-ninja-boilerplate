"""Django Unfold admin configuration.

Separated from common.py to keep settings manageable.
"""

import os
from typing import Any

# FLOWER_URL is set into os.environ by common.py (via the .env loader)
# before this module is imported, so the sidebar can hide the Flower
# link until the operator configures the dashboard.
FLOWER_URL = os.environ.get("FLOWER_URL", "").strip()

UNFOLD: dict[str, Any] = {
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
                    {"title": "Users", "icon": "person", "link": "/admin/core/user/"},
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
                        "link": "/admin/observability/health/",
                    },
                    {
                        "title": "Metrics",
                        "icon": "bar_chart",
                        "link": "/admin/observability/metrics/",
                    },
                    {
                        "title": "Codebase Atlas",
                        "icon": "map",
                        "link": "/admin/atlas/",
                    },
                ],
            },
        ],
    },
    "TABS": [],
}

if FLOWER_URL:
    for section in UNFOLD["SIDEBAR"]["navigation"]:
        if section["title"] == "Monitoring":
            section["items"].append(
                {
                    "title": "Flower (Celery)",
                    "icon": "local_shipping",
                    "link": FLOWER_URL,
                }
            )
            break
