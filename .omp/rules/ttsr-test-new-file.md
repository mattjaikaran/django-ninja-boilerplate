---
description: Interrupts when the agent writes a new test file, to enforce one new test file per task
condition:
  - "def test_"
  - "class Test"
interruptMode: always
scope:
  - "tool:write(**/test_*.py)"
  - "tool:write(**/*_test.py)"
---

# STOP: you are creating a test file

Read "Testing policy" in `AGENTS.md`. Before you continue, answer these:

1. Did you already create a test file in this task? If yes, stop. Put this
   test in that file, or do not write it. One new test file per task, at most.
2. Does a test file for this module already exist? Add to it instead of
   creating a new one.
3. Is this test for a bug fix (regression), a changed public contract, or a
   boundary or permission rule? If not, do not write it.

Do not write tests for wiring, getters, schema echo, default values, copied
constants, or mock calls. Do not add tests to raise coverage.
