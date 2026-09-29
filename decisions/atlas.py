"""Atlas metadata for the decisions app.

The atlas generator reads this module to fill the prose on the map blocks.
See core/atlas.py for the documented shape.
"""

ATLAS = {
    "code": "DC",
    "name": "Decisions",
    "what": (
        "Provider-agnostic System One decision engine. Answers a set of "
        "questions from a piece of state using Laya (in-process), CLM (HTTP "
        "to clm-api), Jev (hosted TypeSafe), or a deterministic fake for "
        "tests. Agent packs route tasks, triage changes, gate actions, and "
        "pick generators."
    ),
    "how": (
        "Route prefixes /decisions and /decisions/agent. The controllers "
        "delegate to DecisionService and AgentDecisionService. "
        "DecisionService selects and caches a provider from the "
        "PROVIDER_REGISTRY and applies per-question escalation thresholds "
        "from DECISION_THRESHOLDS_FILE. Providers fail loud when their "
        "dependency or configuration is missing."
    ),
    "children": {
        "controllers": {
            "name": "Controllers",
            "what": (
                "DecisionController: /evaluate, /similar. "
                "AgentDecisionController: /route-task, /triage-change, "
                "/gate-action, /pick-generator"
            ),
        },
        "services": {
            "name": "Services",
            "what": (
                "DecisionService (providers, escalation), AgentDecisionService "
                "(agent packs), eval and savings measurement, fixture embeddings"
            ),
        },
        "providers": {
            "name": "Providers",
            "what": "base ABC, fake, laya, clm, jev, and the registry",
        },
        "models": {"name": "Models", "what": "DecisionFixture examples"},
        "schemas": {
            "name": "Schemas",
            "what": "Question, request, response, and fixture schemas",
        },
    },
}
