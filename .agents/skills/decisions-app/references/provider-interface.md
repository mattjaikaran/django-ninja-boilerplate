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

- `is_available()` reports whether dependencies and configuration are present.
  It must not raise.
- `predict()` may raise `ImproperlyConfigured` (fail loud) but must never fall
  back to another provider.

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

Laya (and the Jev-compatible API) returns this shape:

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

- `_split_answer` pulls the value from the first key in `ANSWER_VALUE_KEYS`
  (`choice`, `score`, `noul`, `value`) and reads `confidence` beside it.
- `aggregate_confidence` reduces the per-answer values with `min`, because a
  decision is only as trustworthy as its weakest answer.

Worked examples: `decisions/providers/laya.py`, `decisions/providers/jev.py`,
and the deterministic `decisions/providers/fake.py`.

## Testability

Both real providers accept an injected engine or client in `__init__`:

```python
LayaProvider(router=stub_engine)
JevProvider(client=stub_client, api_key="key")
```

Inject a stub and assert the mapping. Then separately assert the fail-loud path
by monkeypatching the module's `_laya_installed` / `_sdk_installed` helper. That
covers the whole provider without installing torch.
