"""Atlas metadata for the decisions app.

The atlas generator reads this module to fill the prose on the map blocks.
See core/atlas.py for the documented shape.
"""

ATLAS = {
    "code": "DC",
    "name": "Decisions",
    "what": (
        "Provider-agnostic System One decision engine. Answers a set of "
        "questions from a piece of state using Laya (in-process), Jev "
        "(hosted TypeSafe), or a deterministic fake for tests."
    ),
    "how": (
        "Route prefix /decisions. DecisionController delegates to "
        "DecisionService, which selects and caches a provider from the "
        "PROVIDER_REGISTRY. Providers fail loud when their dependency or "
        "configuration is missing."
    ),
    "children": {
        "controllers": {
            "name": "Controllers",
            "what": "DecisionController: POST /decisions/evaluate",
        },
        "services": {
            "name": "Services",
            "what": "DecisionService: provider selection, caching, fixtures",
        },
        "providers": {
            "name": "Providers",
            "what": "base ABC, fake, laya, jev, and the registry",
        },
        "models": {"name": "Models", "what": "DecisionFixture examples"},
        "schemas": {
            "name": "Schemas",
            "what": "Question, request, response, and fixture schemas",
        },
    },
}
