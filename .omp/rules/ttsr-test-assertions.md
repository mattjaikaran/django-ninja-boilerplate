---
description: Warns when a test asserts only on mock calls, types, or existence instead of behavior
condition:
  - "\\.assert_(called|called_once|called_with|called_once_with|any_call|has_calls|not_called)\\("
  - "(?m)assert\\s+\\w+(\\.\\w+)*\\s+is\\s+not\\s+None\\s*$"
  - "assert\\s+isinstance\\("
  - "assert\\s+(callable|hasattr)\\("
  - "(?m)assert\\s+True\\s*$"
  - "(?m)assert\\s+len\\([^)]*\\)\\s*(>|!=)\\s*0\\s*$"
question: "Does any test function in this output assert only on mock calls (assert_called*), `is not None`, `isinstance`, `hasattr`, `callable`, `assert True` or `len(...) > 0`, with no assertion on an exact returned value, response status or body, database state, or raised error? Ignore guard asserts that only narrow a type before a real assertion."
scope:
  - "tool:edit(**/test_*.py)"
  - "tool:write(**/test_*.py)"
  - "tool:edit(**/*_test.py)"
  - "tool:write(**/*_test.py)"
---

# This test does not check behavior

A test you wrote asserts only that something was called or exists:

- `mock.assert_called_*`: proves the code called a mock, not that the result
  is right.
- `is not None`, `isinstance(...)`, `hasattr(...)`, `callable(...)`,
  `assert True`, `len(...) > 0`: prove that something exists, not what it is.

Read "Testing policy" in `AGENTS.md`. Assert on an observable result instead:
the response status and body, the database state, the raised error, or the
returned value compared to an exact expected value.

If the test has no behavioral assertion left after this, delete the test.
