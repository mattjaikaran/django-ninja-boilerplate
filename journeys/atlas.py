"""Atlas metadata for the journeys app.

The atlas generator reads this module to fill the prose on the map blocks.
See core/atlas.py for the documented shape.
"""

ATLAS = {
    "code": "JR",
    "name": "Journeys",
    "what": (
        "Lists every user journey with its backend smoke test, Playwright "
        "test, and endpoints, and traces features to the tests that verify "
        "them. Staff see the state of every journey and step."
    ),
    "how": (
        "A pure-Python service reads the journeys table and docs/product/ and "
        "the frontend Playwright JSON report. The admin pages and the "
        "JOURNEYS gate (scripts/check_journeys.py) share it."
    ),
    "children": {
        "services": {
            "name": "Services",
            "what": "Journey table reader, spec parser, e2e evidence reader, sync rules",
        },
    },
}
