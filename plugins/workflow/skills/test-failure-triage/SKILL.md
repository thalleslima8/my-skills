---
name: test-failure-triage
description: Use whenever the test suite fails on a test that already existed (not a new test with no coverage yet) — before touching any assertion, classify the failure as a real regression, an intentional rule change, or flaky/infra, and document the classification in the same turn. Triggers automatically during implementation, bug fixing or any session that runs tests, regardless of which command or agent is active.
---

# Test failure triage

> **Absolute prohibition: no business-rule test may be changed without an explicit classification documented in the same turn.**

When the test suite fails on an **existing test**, follow this protocol before any action.

## Step 1 — Identify and transcribe

For each failing test, transcribe:
- **Test name** (= the rule's contract)
- **Behavior expected** by the test (current rule)
- **Behavior the new code produces** (proposed rule)

## Step 2 — Classify the failure

| Category | Definition | Required action |
|---|---|---|
| **A — Real regression** | The new code broke behavior that should keep working | Fix the code. **Do not touch the test.** |
| **B — Rule changed** | The feature intentionally changes the behavior the test covers | **DO NOT change the test yet.** Ask the user: _"Rule [X] changed from [previous behavior] to [new behavior]. Do you confirm the change?"_ Only after explicit approval: update the test and record "previous rule vs. new rule" in the commit message. |
| **C — Flaky/infra** | Failure unrelated to the logic (timeout, environment dependency, execution order) | Isolate and record it. Do not mask it by adjusting assertions. |

## Step 3 — Document the classification

Before any edit to an existing test, show this in the turn:

```
## Test failure classification

**Test:** TestName
**Category:** A / B / C — [one-sentence justification]
**Action:** [what will be done]
```

A test changed without this block is regression makeup.
