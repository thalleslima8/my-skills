---
name: code-review
description: Use when reviewing a diff, PR, file or code area and the request is to assess quality, not to implement — applies the review checklist (general + layers/architecture + tests) and reports by severity, without fixing anything in this step. Triggers automatically whenever the intent is "review", "take a look", "find problems", regardless of which command or agent is active.
---

# Code review checklist

Execution rules, any stack:
1. Discover the scope — `git diff`, files modified since the last commit, or the directory the user indicated.
2. Read the main files; use an exploration agent if deeper investigation is needed.
3. Analyze against the checklist below.
4. Produce a report: executive summary, findings per file/category (location `file:lines`, problem, impact, suggestion), grouped by severity (critical/important/improvement).
5. **Do not fix anything in this step** — only report. Fixing is a separate round, only after confirmation.

## General checklist (any stack)

- Code is easy to understand · clarity over cleverness
- Names reveal intent
- Clear responsibility per method/class/function
- Controlled complexity — no unnecessary nesting or branching
- Comments explain the why, not the what
- Follows patterns already adopted in the rest of the project
- Errors handled explicitly and consistently (result/error types, domain exceptions — per the project's pattern)
- Testable — no hidden dependencies that are hard to isolate
- External input is validated
- No improper exposure of sensitive data (logs, error messages, API responses)

## Layers/architecture (adapt to the project's stack)

- Business rules live in the correct layer, per the architecture declared in the project's CLAUDE.md — never scattered across entry points (endpoints, controllers, handlers) or the persistence layer
- Thin entry points — parsing/routing only, delegating logic to the application/domain layer
- The persistence layer only persists — no business rules leaking in
- DTOs and domain entities are not mixed up
- Efficient, predictable queries (no obvious N+1, no fetching more data than needed)
- Logs help diagnosis without leaking sensitive data
- Validations are consistent with the domain invariants
- Dependency direction between modules/layers is respected (see the project's CLAUDE.md)

### Example — .NET backend (optional, illustrative)

> This section is an example of how the checklist above is instantiated on a concrete stack. Use it as a reference if the project is .NET; for another stack, ignore it and apply the generic checklist above.

- Business rules in the application layer (services), never in controllers/endpoints or data access
- Thin endpoints/controllers — no business logic, only request parsing and a call to the service
- Repositories only persist, following the project's Repository pattern
- Services return an explicit success/error type (e.g. `Result`/`Error`) instead of relying only on exceptions for expected control flow
- Tests follow the mock/fixture patterns already present in the project (e.g. xUnit + Moq + AutoFixture, or whatever the CLAUDE.md declares)

## Tests

- Cover the relevant behavior, not just the happy path
- Happy, invalid and edge-case scenarios are covered
- Readable and easy to maintain — the test name describes the contract it exercises
