# Provider interface

`decisions/providers/base.py` defines the contract.

## The ABC

```python
class DecisionProvider(ABC):
    name: str = "base"

    @abstractmethod
    def predict(self, state: dict[str, Any], questions: dict[str, Any]) -> DecisionResult: ...

    @abstractmethod
    def is_available(self) -> bool: ...
```

- `is_available()` reports whether required configuration is present without
  making a decision request. It does not guarantee a remote service is healthy.
- `predict()` fails loud on missing dependencies or remote errors. It never
  switches to another provider.

## The result

```python
@dataclass(frozen=True, slots=True)
class DecisionResult:
    answers: dict[str, Any]              # question key -> value
    answer_confidence: dict[str, float]  # question key -> provider confidence
    confidence: float                    # aggregate: the minimum
    provider: str
    routing: dict[str, Any] | None = None
    fallback_used: bool = False
    escalation_recommended: bool = False
```

## Normalising a vendor response

Laya returns mappings, while Jev returns typed SDK answer objects and CLM
returns the same typed answers over HTTP:

```python
{
    "answers": {
        "department": {"choice": "billing", "confidence": 0.94},
        "urgency": {"score": 0.8, "confidence": 0.71},
        "churn_risk": {"noul": True, "confidence": 0.88},
    },
    "routing": {"model": "english", "repo": "...", "reason": "..."},
}
```

Call `result_from_raw(raw, self.name)` once and let the helpers do the rest:

- `_split_answer` reads `choice`, `score`, `noul`, or `value` from either
  a mapping or a typed answer object. A `noul` probability without separate
  confidence uses `max(p, 1-p)` for selected-side confidence.
- `aggregate_confidence` reduces the per-answer values with `min`, because a
  decision is only as trustworthy as its weakest answer.

Worked examples: `decisions/providers/laya.py`, `decisions/providers/clm.py`,
`decisions/providers/jev.py`, and `decisions/providers/fake.py`.

## Testability

Every provider accepts an injected engine or client in `__init__`. For CLM,
inject an `httpx.Client` with `MockTransport`; do not call an external model
from unit tests. Run a real Laya prediction separately after installing the
base dependencies to verify that the default checkpoint loads.
