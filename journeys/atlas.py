"""Atlas metadata for the journeys app.

The atlas generator reads this module to fill the prose on the map blocks.
See core/atlas.py for the documented shape.
"""

ATLAS = {
    "code": "JR",
    "name": "Journeys",
    "what": (
        "Traces product features to user journeys and to the Playwright "
        "tests that verify them. Staff see the state of every step."
    ),
    "how": (
        "A pure-Python spec service reads docs/product/ and the frontend "
        "Playwright JSON report. The admin pages and the JOURNEYS gate "
        "(scripts/check_journeys.py) share it."
    ),
    "children": {
        "services": {
            "name": "Services",
            "what": "Spec parser, e2e evidence reader, sync rules",
        },
    },
}
