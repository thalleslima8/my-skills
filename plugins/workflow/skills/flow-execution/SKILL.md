---
name: flow-execution
description: /flow's execution mode — the run that implements epics up to a single pull request (pre-flight, order, branch, spike slices, review gate, polish, commit, CI, pull request, comment rounds, stop and resume). Use ONLY when the /flow command tells you to load it, after an explicit request to implement or to continue a run. Never start it on your own, and never from another command or agent.
user-invocable: false
---

# /flow — execution mode

This skill is the second half of the `/flow` command and is always read with it. The command decides the mode and holds the mediation rules; when this skill says "the mediation steps" or "the mediation round rules", it means the command's "Mediation mode" section. The command's "Both modes" rules apply here too.

You **conduct** the run: the `spike` agent implements each epic, the architect and the analyst settle what the spike cannot decide alone, the `code-review` skill gates each epic, and you own the git side. You write no product code.

## Execution cycle

```
[E0] PRE-FLIGHT          → clean session · clean tree or a run to resume · gh ready · CI triggers, standards sources and verify commands read
[E1] SCOPE AND ORDER     → in-progress first, then backlog; declared dependencies or an ordering round
[E2] BRANCH              → flow/<yyyy-mm-dd> from the default branch (or the branch of the run being resumed)
[E3] PER EPIC, in order
  [E3.1] SPIKE SLICES    → ≤ 3 phases per call + DA-### + standards sources + verify commands → DONE | BLOCKED | HANDOFF
  [E3.2] BLOCKED         → specialist rounds (interface → design-an-interface here) → answer → continue the spike
           └─ critical, no consensus → STOP
  [E3.3] HANDOFF         → new spike call from the handoff and the checklist → [E3.1]
  [E3.4] REVIEW GATE     → code-review in this session, once per epic; blocking findings → fix round by class (max 2)
           ├─ re-gate on the delta only; 3rd fail → STOP
           └─ pass → one polish round for the non-blocking findings
  [E3.5] COMMIT + PUSH   → one commit per epic, by you; draft PR on the first push when CI is pull_request-only
  [E3.6] CI              → watch; flaky/infra → 1 re-run; red → spike + triage → fix commit (max 2) → 3rd fail → STOP
  [E3.7] SESSION BUDGET  → 12 or more agent calls in this session → STOP at this boundary; a new session resumes
[E4] CHECKPOINT          → PR description, PR opened or marked ready → STOP: hand over to the user
[E5] COMMENT ROUND       → only when the user says so, in a new session: unresolved comments → spike → gate → commit → CI → reply with SHA → [E4]
[E6] APPROVED            → the user says it is approved → END (the merge is the user's)
```

There is no approval inside the cycle: the order of the epics, the decisions settled by the specialists and the provisional ones all go into the pull request description, which is the single checkpoint.

**Sub-agents cannot spawn sub-agents.** The spike runs as a sub-agent, so everything that spawns agents runs in **this** session: the `code-review` skill (two sub-agents) and the `design-an-interface` skill (three or four). The spike never runs them.

---

## Models

Every call names its model, or takes it from its agent definition, so the cost of a run does not depend on the model this session happens to use:

| Call | Model |
|---|---|
| `spike` — implementation and fix rounds | The agent's own (`opus`): the implementation is where a stronger model saves rounds |
| `arquiteto`, `analyst` | The agents' own (`sonnet`) |
| `code-review` and `design-an-interface` sub-agents | `model: "sonnet"`, as those skills say |
| This session | The user's choice. It follows a procedure and writes no product code, so it runs well on `sonnet` |

Pass a different `model` on a call only when the user asked for it in the request ("run the spike on sonnet"). If this session runs on a larger model than `sonnet`, say once, in your first status line, that the run works the same with `/model sonnet` and that the spike keeps its own model. Do not stop for it.

---

## E0 — Pre-flight

0. **A clean session.** A run starts in a session that carries nothing else. If this session already ran a mediation (it made any `Agent` call before this request), do not start: the epics are on disk and nothing is lost. Say "This session already carries a mediation. Start a new session and ask `/flow` to implement {the same request} — the run reads the epics from disk." Go on in this session only if the user's request says to run here.
1. **Working tree.** `git status --porcelain` must be empty, unless you are resuming a run (see "Stop and resume"). Otherwise stop, touch nothing, and ask: "The working tree has changes that do not belong to a `/flow` run. Commit, stash or discard them, then ask again?"
2. **GitHub.** `gh auth status` succeeds and the repository has a GitHub remote. If not, stop and say what is missing.
3. **Default branch.** `gh repo view --json defaultBranchRef -q .defaultBranchRef.name`.
4. **CI triggers — a fact, never a question.** Read `.github/workflows/*.yml` and `*.yaml`:
   - a workflow runs on `push` to the run's branch (no `branches` filter, or one that matches `flow/**`) → **push CI**: the pull request is opened at the end (E4);
   - otherwise, a workflow runs on `pull_request` against the default branch → **PR-only CI**: the pull request is opened **as draft** on the first push and marked ready at the end;
   - neither (no workflows, or none reaches this branch or its pull request) → **no CI**: the spike's local test runs are the only validation, and the pull request says so.
   A `paths` / `paths-ignore` filter can leave a commit without a run: that is "no run for this commit", not a failure, and the pull request says so.
5. **Project conventions.** Commit, pull request title and branch rules in the project's `CLAUDE.md` apply on top of this cycle where they do not contradict it (the branch name and the one-commit-per-epic rule are this cycle's).
6. **Standards sources — collected once per run.** Run step 2 of the `code-review` skill ("Collect the standards sources") now, over the whole repository instead of one diff's touched files. Keep the list: each file's path, what it is and its scope — never its contents. It goes to every spike call in `[STANDARDS SOURCES]`, so the spike builds its rule register from the same sources the review uses, and to every gate, which picks from it by touched files instead of collecting again. No `docs/standards/` in the project → the list says so.
7. **Verification commands — a fact, never a question.** From the workflows read in step 4, take the commands the CI runs to build, lint/format and test (the `run:` steps), in order. With no CI, take the build, lint and test commands the project's `CLAUDE.md` declares (or its README, Makefile or package manifest). They go to every spike call in `[VERIFY]`: the spike validates with what the CI will run, on the whole suite. Nothing declared anywhere → `[VERIFY]` says "none declared".

---

## E1 — Scope and order

**Scope.** With no argument: every epic in `in-progress/`, then every epic in `backlog/` (if the project uses that convention). With an argument: only the epics the user named (slug, path or title); a name that matches no epic stops the run with that message. An epic with no pending `- [ ]` item gets no spike call and is listed as "nothing pending" in the final report.

**Order.**

1. `in-progress/` first, then `backlog/`.
2. Inside each folder, the same rule: when the epics declare dependencies on each other (a `Depends on:` line or an explicit prerequisite epic), follow them (topological order); when they do not, run an **ordering round** (below).
3. An epic that depends on an epic outside the scope that is not in `done/` is left out of the run and listed as skipped, with the reason.

The order is **not** submitted to the user: it goes into the pull request description with its reason.

### Ordering round

Same rules as a mediation round: independent calls (architect first, then analyst), cross-check, at most 1 counter-argument. One question per epic of the folder plus one for the folder's overall order. When both folders need a round, put both folders' questions in the same calls; `in-progress/` epics still come before `backlog/` ones.

```
[EXECUTION RUN — ORDER THE EPICS]
Epics to implement in {in-progress/ | backlog/}{, after: {slugs already ordered before this folder}}:
- {slug} — {title}: {3-line summary: goal, layers touched, main DA-### titles}
- ...

[ROUND QUESTIONS]
Q{n} — Which of these epics must come before {slug}, and why? ("none" is a valid answer)
...
Q{m} — The full implementation order.

[TASK]
Answer each Q number from your perspective ({architect: technical dependency — code, schema or contract one epic needs from another, and risk | analyst: functional dependency — a flow or rule one epic needs from another, and value}). 1-2 lines of justification each. Write "outside my area" when it is.
```

Converged → that order. Still diverging after the counter-argument → the architect's order where the conflict is a technical dependency, the analyst's where it is functional; the pull request marks that part of the order as decided by that specialist. Never ask the user.

---

## E2 — Branch

```
git fetch origin
git switch -c flow/<yyyy-mm-dd> origin/<default-branch>
```

If `flow/<yyyy-mm-dd>` already exists (locally or on `origin`): with an open pull request, it is the run to resume (see "Stop and resume"); with a merged or closed one, use the next free suffix (`flow/<yyyy-mm-dd>-2`). Read the epics after switching, so the run starts from the default branch's state.

---

## E3.1 — Calling the spike

**Slice first.** The spike gets a bounded slice per call. You decide the slices from the epic's checklist; the spike's own sense of its context is not the limit. A slice is at most **3 pending phases or 12 pending `- [ ]` items**, whichever comes first, in the epic's order; a phase with more than 12 pending items goes alone. Each slice is a fresh call, and the review gate runs once per epic, after the last slice.

```
Agent(subagent_type: "spike", prompt: <block below>)
```

`spike` is this plugin's agent (listed as `workflow:spike`). It carries its own instructions: never paste the `/spike` command's file into the prompt, nor tell the agent to read it.

```
[EPIC]
{path} — {title}

[PHASES]
{this slice: each phase with its pending `- [ ]` items, read from the epic file now}
Slice {i} of {n}{ — last slice: write the commit message for the whole epic}

[PREVIOUS SLICES]
{each earlier slice's `Summary` and `Bug fixes on the way`, verbatim from its DONE block — or "none"}

[DECISIONS IN FORCE]
{DA-### — one line — (epic | consensus | user | architect, provisional | analyst, provisional)}

[ANSWERS]
{Qn — answer — (consensus | user | architect, provisional | analyst, provisional) — recorded as DA-###; or "none"}

[STANDARDS SOURCES]
{the E0 list: path — what it is — scope; or "no documented standards found"}

[VERIFY]
{the E0 verification commands, in order, exactly as the CI runs them — or "none declared: use the commands the project documents"}

[HANDOFF]
{the previous call's HANDOFF block verbatim, or "none"}

[FIX REQUEST]
{"none", or a fix round — see E3.4, E3.6 and E5}

[NEXT QUESTION NUMBER]
Q{n}

[TASK]
{a slice: "Build the rule register, implement the phases in order and run the definition of done." | fix round: "Address the fix request." | after a block: "Continue from where you stopped, applying the answers."}
End with exactly one DONE, BLOCKED or HANDOFF block.
```

Send only what the call needs: the slice's phases (not the done ones, not the later ones), the `DA-###` that bear on them, and this run's answers. Never the run's history.

**Continuing the same agent.** When the spike's next input belongs to the work it just did — the answers to its `BLOCKED`, an incomplete `DONE`, a `review` fix round, a `polish` round — continue that agent with `SendMessage` (to the agent id its result gave) instead of starting a new one: it keeps what it read and wrote. Send only the blocks that changed (`[ANSWERS]`, `[FIX REQUEST]`, `[TASK]`). Make a fresh call with the full block when the agent cannot be continued: a new session, `SendMessage` not available or failing, a `HANDOFF`, a new slice, or a `ci` or `pr-comments` round. For a review or polish round after the last slice, the agent to continue is the last slice's.

| The spike returns | Next |
|---|---|
| `DONE`, more slices pending | Check that the epic's checklist shows the slice's items as `- [x]` and that `git status` shows the changes; keep its `Summary` for `[PREVIOUS SLICES]`; next slice |
| `DONE`, last slice | The same checks; then E3.4 (or, in a fix round, back to the step that asked for it) |
| `BLOCKED` | E3.2 |
| `HANDOFF` | E3.3 |
| No block, or a malformed one | Continue the agent once with "End with one DONE, BLOCKED or HANDOFF block." A second miss stops the run |

---

## E3.2 — Resolving a BLOCKED

The block carries one or more questions, each with its `Kind`: `question`, `divergence`, `interface` or `rule-change`. Resolve them together, each by its kind, and answer them all in one message to the spike (E3.1, "Continuing the same agent"). A question whose answer is a fact the spike could have looked up in the code goes back to it as an instruction to look it up.

### Kind `question` or `divergence` — specialist rounds

Run the mediation rounds on the questions (steps 2–5: independent calls, cross-check, at most 1 counter-argument per question, at most 4 rounds if the answers open new questions), with this round prompt:

```
[EPIC]
{path} — {title}; phase in progress: {phase}

[DECISIONS IN FORCE]
{the DA-### that bear on the questions, one line each}

[SETTLED SO FAR]
{this run's answers that bear on the questions: Qn — decision — (consensus | user | provisional)}

[BLOCKED BY THE IMPLEMENTATION]
Q{n} — {question}
  Kind: {question | divergence | rule-change}
  Context from the code: {the spike's context, verbatim}
  Location: {file:line, ...}
  Options the developer sees: {verbatim, or "none"}

[TASK]
Answer every question from your perspective ({architect: technical architecture | analyst: functional/domain, with your default critical stance}).
For each question, keep its Q number, give your answer and 1-3 lines of justification, then one line:
Critical: yes | no — yes only if (a) no answer lets the epic go on without rethinking it (false premise, missing external dependency, the epic's goal in question), (b) only the user can decide it (goal, priority, budget, acceptable risk, business approval), or (c) it is hard to reverse (say what makes it so).
- Outside your area → write "outside my area".
- A decision in force creates a real problem → flag it explicitly.
```

Counter-argument: the mediation step 5 prompt, with `[EPIC]` in place of `[POINT UNDER DISCUSSION]`.

**Classify each question.** It is **critical** when either specialist marks it critical with a reason that holds, or when you see that it meets (a), (b) or (c) yourself.

| Outcome | What happens |
|---|---|
| Converge | Settled by consensus — whether or not it is critical, including (b) → `DA-###` in the epic → answer to the spike |
| Critical (a, b or c), still diverging after the counter-argument | **STOP** |
| Not critical, still diverging after the counter-argument | The area's specialist decides (architect for technical questions, analyst for functional ones) → provisional decision prompt → `DA-###` marked **provisional** → answer to the spike |

**Provisional decision prompt** (to the area's specialist only):

```
[EPIC]
{path} — {title}

[QUESTION WITHOUT CONSENSUS]
Q{n} — {question}
  Your answer: {1-2 line synthesis}
  The other side: {2-4 line synthesis}

[TASK]
This question is in your area and is not critical, so you decide it now; the user confirms or reverts it on the pull request.
Reply with:
Decision: {one sentence, phrased as a DA-### entry}
Why: {1-2 lines}
To revert: {what changes in the code if the user picks the other side, 1 line}
```

**Recording.** You write each decision into the epic, continuing its `DA-###` numbering and following the format of its existing entries: the decision, the justification, and how it was settled — `consensus`, `user`, or `provisional — decided by {architect|analyst}; other view: {1 line}; to revert: {1 line}`. Fact answers are not decisions and get no `DA-###`.

### Kind `interface` — design-an-interface, run here

The spike stops before writing the code of a frontend module whose interface is not decided yet. Run the `design-an-interface` skill in this session, on the module, callers and constraints in the block, with the overrides in its "Under /flow's execution mode" section: the framing goes to the architect instead of the user, you give no recommendation of your own, the **architect picks**, the **analyst validates**, and the choice becomes a `DA-###`.

```
[EPIC]
{path} — {title}

[MODULE]
{module, what it is for, its callers}

[FRAMING]
{the skill's step 1 framing: requirements, constraints, the frontend rules that bind it by ID}

[DESIGNS]
Design {A} — {constraint}: {interface, usage examples, what it hides, accessibility ownership, trade-offs}
...

[COMPARISON]
{the skill's step 4 comparison}

[TASK]
Pick the interface to implement: one design, or a hybrid you state precisely.
Reply with: Choice, the interface restated in one block (signature plus one usage example), why (2-3 lines), and "ADR candidate" when it is hard to reverse, surprising without context and a real trade-off.
```

```
[EPIC]
{path} — {title}; the use cases and acceptance criteria this module serves, quoted

[CHOSEN INTERFACE]
{the architect's restated interface}

[TASK]
Does this interface support every use case and state the epic requires (including empty, error, loading and permission states)?
Reply "valid" with 1-2 lines, or name each use case it fails and why.
```

"Valid" → `DA-###` (consensus). An objection → one counter-argument to the architect with a synthesis of it; converged → `DA-###` (consensus); still diverging → the table above: critical (a, b or c) → **STOP**; not critical → the interface's shape is a technical question, so the architect's choice as `DA-###` (provisional). The restated interface goes to the spike in `[ANSWERS]`.

### Kind `rule-change` — test-failure-triage category B

An existing test fails because the implementation changes the rule it covers. It goes through the same specialist rounds as `question` and `divergence` (round prompt above, `Kind: rule-change`), with the test's name, the rule the test expects, the behavior the new code produces and the `DA-###` and acceptance criteria that bear on the rule in its context. The question is whether the rule should change the way the code changes it. The outcome follows the same table: consensus or a provisional decision → the answer goes to the spike; a critical question without consensus → **STOP**.

- **The rule changes** → "category B confirmed by {DA-###}"; the spike updates the test and records the previous versus the new rule in the commit message.
- **The rule stays** → the failure is a regression (category A); the spike fixes the code and leaves the test alone.

---

## E3.3 — HANDOFF

The spike stopped before the end of its slice because its context got heavy. Make a fresh spike call with the `HANDOFF` block verbatim and the slice's still-pending phases read **from the epic's checklist now** — the checklist is the source of truth for where to resume; when the handoff disagrees with it, the checklist wins. Two handoffs in a row with no item newly marked `- [x]` mean no progress: **STOP**.

---

## E3.4 — Review gate

When the last slice returns `DONE` for the epic:

0. **Check the `DONE` block before spending a review.** `Verify` shows every `[VERIFY]` command run on the whole suite and passing, `Rules`, `Obligations` and `Claims` are filled in, and `Gaps` is "none". Anything missing or failing → continue the spike: "Finish the definition of done: {what is missing}." This is allowed once per epic; a second incomplete `DONE` counts as a failed gate.
1. **First gate.** Run the `code-review` skill in this session, in its **gate mode**: scope `git diff HEAD` plus the untracked files, spec = the epic's path, the standards sources from E0, no closing question. Its "Gate mode" section defines which findings are blocking. Then run `git add -A`: the index is now the snapshot of what this gate reviewed, and what the spike changes next shows up as `git diff`.
2. **Pass** → step 6 (polish).
3. **Fail** → a fix round: continue the spike (E3.1, "Continuing the same agent") with

   ```
   [FIX REQUEST]
   Kind: review
   F{n} — {rule ID} ({level}) — {every location the gate found} — {problem} — {the fix the rule implies}
   ...
   Fix the class, not the instance: each finding names a rule. Sweep the whole change (source, tests, fixtures, docs) for every other occurrence of that rule and fix them all.
   Upheld earlier (fix, do not contest): {F numbers, or "none"}
   ```

   Non-blocking findings stay out of this request: they wait for the polish round.

4. The spike fixes each blocking finding or contests it in its `DONE` block. Contested findings are **arbitrated in a single round**, no counter-argument: the architect for Standards findings, the analyst for Spec findings.

   ```
   [EPIC]
   {path} — {title}

   [CONTESTED FINDINGS]
   F{n} — {rule ID} ({level}): "{rule, quoted}" — {location}
     Hunk: {quoted}
     Review says: {problem and fix}
     Developer says: {the spike's reason, verbatim}
   ...

   [TASK]
   For each finding, one of:
   - upheld — {Standards: the rule applies and the code breaks it | Spec: the requirement is missing or wrong}
   - dropped — the finding is wrong (the rule does not apply here, the code does not break it, or the requirement is met); say why
   - deviation accepted — Standards SHOULD rules only: the reason is sound; give the one-line justification for the pull request
   A MUST rule cannot be accepted as a deviation.
   One line of justification each. This is a single round: there is no follow-up.
   ```

   - **Upheld** → stays open, and the spike may not contest it again.
   - **Dropped** → gone; the pull request lists it with the reason only when it was a Spec finding.
   - **Deviation accepted** → a justified SHOULD deviation: in the pull request and in the epic's commit body.

   **A new exception to a MUST rule** is not arbitrated here. The spike asks for it in a `BLOCKED` block (kind `question`, citing the rule ID and the reason), and it goes through E3.2 like any other question: consensus → a `DA-###` that cites the rule ID, which makes the violation `excepted`; critical without consensus → **STOP**; not critical without consensus → the area's specialist decides, as a provisional `DA-###`. When the exception is not granted, the finding keeps failing the gate and counts toward the review limit below.
5. **Re-gate on the delta.** Run the gate again as a **delta gate** (see the skill's "Gate mode"), passing the open findings (F number, rule, locations) and the deviations the architect accepted so far. It confirms each open finding is closed across the whole change, and looks for new findings only in what changed since the snapshot (`git diff` plus the untracked files). A new finding in code the fix round did not touch is a **late finding**: it never blocks and goes to the polish round. Then `git add -A` again. **At most 2 fix rounds per epic for the review**: the third failed gate stops the run.
6. **Polish — one round per commit, after the gate passes** (the epic's commit, or the commit of a `ci` or `pr-comments` round). The gate leaves non-blocking findings: MAY rules, baseline judgement calls, Spec findings (claims included) and late findings. With none, go to E3.5. Otherwise continue the spike with

   ```
   [FIX REQUEST]
   Kind: polish
   N{n} — {F number} — {rule ID, spec line or claim, quoted} — {location} — {problem} — {the suggested fix}
   ...
   Fix each one that is right and within the epic's scope; decline the rest with a one-line reason.
   ```

   Then run one delta gate over the polish changes, with the `N` items as open findings, and `git add -A`. A blocking finding in that delta is a review fix round like any other and counts toward the limit of 2. There is **no second polish round**: what the spike declined, what is still open and any new non-blocking finding go to the pull request. `not verifiable` rules are never polish items; they go straight to the pull request.

Spec findings never block; they go to the polish round, and what is left of them goes to the pull request. The same holds for the non-blocking Standards findings (MAY, baseline smells).

---

## E3.5 — Commit and push — done by you, never by the spike

1. The tree holds only this epic's changes (it was clean when the epic started). The spike has already moved the epic file (`backlog/` → `in-progress/` → `done/` when the last phase is done), so that move goes in this commit.
2. Take the message from the spike's `DONE` block and check it against the `conventional-commit` skill: imperative subject; a body that explains why and carries `Epic: {slug}`. Then add to the body everything the pull request description needs from this epic, so a resumed run can read it back from `git log`:
   - `Decisions:` the relevant `DA-###`, marking the ones settled in this run and the provisional ones as such;
   - `Deviations:` each SHOULD deviation the architect accepted — `{rule ID} — {reason}`;
   - `Non-blocking findings:` the MAY findings, baseline smells and late findings still open after the polish round (with the spike's reason when it declined one), and the `not verifiable` rules;
   - `Spec findings:` the Spec axis findings still open after the polish round, unconfirmed claims included (and the arbitration outcome, when contested).

   Leave out a heading that would be empty. The project's `CLAUDE.md` commit rules apply on top.
3. `git add -A`, then `git commit -F <message file>`. Never `--no-verify`: a failing hook is treated like a failed review gate (fix round, same limit).
4. `git push -u origin <branch>` the first time, `git push` after. **Never force-push.** A rejected push means someone else wrote to the branch: **STOP** and report.
5. **PR-only CI and no pull request yet:** `gh pr create --draft --base <default-branch> --head <branch> --title "<title>" --body-file <file>`, with the description template filled in as far as the run has got. After each later epic, refresh it with `gh pr edit <n> --body-file <file>` so the pull request carries the run's state. Title: the project's convention if `CLAUDE.md` has one, otherwise `flow {yyyy-mm-dd}: {epic slugs, or "N epics"}`.

---

## E3.6 — CI

After every push, unless the run has **no CI**:

- With a pull request: `gh pr checks <n> --watch`.
- Push CI without a pull request: `gh run list --branch <branch> --commit <sha> --json databaseId,name,status,conclusion` until the runs appear, then `gh run watch <id> --exit-status` for each.

**Green** → E3.7, then the next epic. **Red** →

1. Read the failure: `gh run view <id> --log-failed`.
2. **Flaky or infra** (runner or network error, a service outage, a timeout, a cancelled job, a failure unrelated to the change): `gh run rerun <id> --failed` **once** before counting it. The same applies when the spike's triage classifies it as category C without a code change.
3. Otherwise, a fix round, in a fresh spike call (E3.1's block, with `[PHASES]` "none — fix round"):

   ```
   [FIX REQUEST]
   Kind: ci
   Workflow / job / step: {names}
   Run: {url}
   Log excerpt: {the failing part, at most 60 lines}
   ```

   The spike applies `test-failure-triage` (a category B returns as a `BLOCKED` of kind `rule-change`), fixes, and returns `DONE` with a `fix(scope): ...` message that references the epic's slug.
4. The fix goes through the review gate (E3.4, same rules, and its rounds count toward the epic's review limit; the tree was clean after the epic's commit, so `git diff HEAD` is the fix alone), then its own commit and push (E3.5), then CI again.
5. **At most 2 fix rounds per epic for CI**, counted apart from the review rounds: the third red run, after its re-run when it qualified for one, stops the run.

---

## E3.7 — Session budget

At every epic boundary (the epic is committed, pushed and green), count the `Agent` and `SendMessage` calls this session has made since it started. **12 or more → stop here**, even with epics left, and show the resume message from "Context control" below. It is a count, not an impression: a session that has driven that many sub-agents re-reads a long history on every step, and a new session rebuilds the run from the epics' checklists, the branch and the pull request at a fraction of the cost. Never stop in the middle of an epic for this.

---

## E4 — Checkpoint: the pull request

When every epic in scope is committed, pushed and green (or the run has no CI):

1. Write the description (template below). If the repository has `.github/pull_request_template.md`, keep its sections and checklist and fit this content into them.
2. PR-only CI: `gh pr edit <n> --body-file <file>`, then `gh pr ready <n>`. Push CI or no CI: `gh pr create --base <default-branch> --head <branch> --title "<title>" --body-file <file>`.
3. **Stop** and hand over:

   ```
   **/flow — {N} epics ready for review:** {pull request URL}
   - Order: {slug → slug → ...}
   - Provisional decisions to confirm or revert: {count, or "none"} (listed in the pull request)
   - CI: {green | no CI}
   Review it on GitHub. When you have commented, start a new session and tell `/flow` so: it picks the run up from the branch and the pull request, and I do not watch the pull request. Resolving threads and the merge are yours.
   ```

### Pull request description template

```markdown
## Summary
{1-3 lines: what this run implemented}

## Epics — order and why
1. `{slug}` — {why it comes here} — {sha} `{commit subject}`
   - Fix commits: {sha} `{subject}` ({review | ci})
2. ...

Order source: {declared dependencies | ordering round — consensus | ordering round — {architect|analyst} decided {which part}}
Not implemented: {skipped epics and why, epics with nothing pending, or "none"}

## Decisions made during the run
| DA | Epic | Decision | Settled by |
|---|---|---|---|
| DA-### | `{slug}` | {decision} | consensus · user · **provisional** ({architect|analyst}) |

### ⚠️ Provisional — confirm or revert
- **DA-###** (`{slug}`) — {decision} — decided by {architect|analyst} · other view: {1 line} · to revert: {1 line}

## Justified SHOULD deviations
- `{rule ID}` — {location} — {reason accepted by the architect}

## Non-blocking review findings
### MAY rules and baseline smells
- `{rule ID}` or possible {smell} — {location} — {suggestion}
### Rules not verifiable
- `{rule ID}` — {what would be needed to verify it}
### Spec axis (information only)
- `{slug}` — {missing or partial | scope creep | looks wrong} — {spec line, quoted} — {location}

## CI
{workflow — status — run URL, per epic; re-runs and why; "no CI configured" or "no run for this commit" when that is the case}

---
Epics moved to `done/` are implementation bookkeeping, not business approval — that and the merge are the reviewer's.
```

Leave a section out when it is empty, except "Decisions made during the run" and "CI", which say "none" instead.

---

## E5 — Comment round

Starts only when the user says they have reviewed or commented. **Never poll the pull request.**

0. **A fresh session.** A comment round runs in a session of its own. If this session is the one that implemented the epics (it made spike calls for them), do not start the round: say "Start a new session and tell `/flow` you commented on the pull request — it resumes from the branch and the pull request." Go on here only if the user says to.
1. **Fetch only what is pending.**
   - Review threads, with their resolved state:

     ```
     gh api graphql -f query='query($owner:String!,$name:String!,$pr:Int!){repository(owner:$owner,name:$name){pullRequest(number:$pr){reviewThreads(first:100){nodes{id isResolved isOutdated path line comments(first:50){nodes{author{login} body createdAt url}}}}}}}' -F owner={owner} -F name={repo} -F pr={n}
     ```

     Keep the threads with `isResolved: false`. A thread whose last comment is your reply (it carries the `<!-- /flow -->` marker) and has nothing newer from the user is waiting for the user: skip it.
   - Review bodies (`gh api repos/{owner}/{repo}/pulls/{n}/reviews`) and general comments (`gh api repos/{owner}/{repo}/issues/{n}/comments`): only those posted after your last reply that carries the marker.
2. **Triage each comment.**
   - **Change request** → goes to the spike.
   - **Question** → answer it in the thread from the epics, the `DA-###` and this run's records; when it needs a technical or functional opinion, one call to the area's specialist.
   - **Contradicts a project standard** → do not apply it silently: reply in the thread quoting the rule (`{rule ID}` ({level}): "{rule}") and asking the user to confirm. Apply it in a later round only after the user confirms there: a MUST rule then gets a `DA-###` exception citing the rule ID (settled by the user); a SHOULD rule, a justified deviation in the description.
   - A comment that changes scope, the goal or an epic's decision is the user deciding: apply it, record the `DA-###` (user), and say so in the reply.
3. **Fix round:** one fresh spike call per epic touched (or one call when the comments span epics; E3.1's block, with `[PHASES]` "none — fix round"), with

   ```
   [FIX REQUEST]
   Kind: pr-comments
   C{n} — {path:line | general} — {author}: "{comment}" — {url}
   ...
   ```

   `BLOCKED` blocks are resolved as in E3.2.
4. Review gate (E3.4) on `git diff HEAD`, same rules and limits, with the comments as the spec: the Spec axis reports each comment still missing or partly addressed. The polish round applies here too, so a comment is not left half answered.
5. **One commit per comment round** (E3.5), its body listing the comments addressed (URLs) and the epic slugs touched; push; CI (E3.6), same limits.
6. **Reply in every thread you handled**: `Addressed in {sha}: {1 line}.` followed by `<!-- /flow -->` — through `addPullRequestReviewThreadReply` (`gh api graphql`) for review threads, and one `gh pr comment <n>` quoting each handled point for review bodies and general comments. **Never resolve a thread** — that is the user's.
7. Update the description when the round added decisions, deviations or findings, then hand over again as in E4.

## E6 — Approved

When the user says the pull request is approved, end the session: "The merge is yours." Do not merge, do not delete the branch, do not mark any epic as business-approved.

---

## Stop and resume

**The run stops** on: a critical question still without consensus after the counter-argument, a third failed review gate or a third red CI on the same epic, a spike with no progress or no valid block twice, a rejected push, or a dirty tree that is not a run to resume. The pull request (E4) is the planned stop, and the session budget (E3.7) is a planned pause at an epic boundary, with nothing pending.

**What stays:** the epics already approved stay committed and pushed. The partial work of the stopped epic **stays in the working tree, uncommitted** (part of it may be staged: the index is the last gate's snapshot). For a question, write it into that epic as a pending decision, following the epic's format, so a new session finds it:

> Pending decision (critical): Q{n} — {question} — Architect: {1 line} · Analyst: {1 line}

**The brief to the user:**

```
**/flow stopped — {reason}.**

**Done:** {each committed epic: slug — sha — CI status}; pull request: {URL, draft or ready, or "not opened yet"}
**Stopped at:** `{slug}` — {phase}; partial work uncommitted in the working tree ({N} files)

**Question:** Q{n} — {question}
- **Architect:** {1-2 lines} · **Analyst:** {1-2 lines} · **Where they diverge:** {1 sentence}
{or, for a third failure: the findings or the CI failure still open, and what each of the two fix rounds tried}

To go on: answer here, or start a new session and ask `/flow` to resume the implementation, with your answer.
```

**Resume.** There is no state file: the state is rebuilt from the epics' checklists, the `flow/*` branch and its pull request.

1. Find the run: the current branch if it is `flow/*`, otherwise the most recent `flow/*` branch with an open pull request (`gh pr list --head <branch> --state open`). Switch to it only when the tree is clean.
2. A dirty tree on that branch is the stopped epic's partial work: accept it. A dirty tree anywhere else is E0's stop. What is staged there is an earlier gate's snapshot and means nothing to the new session: the resumed epic's first gate reviews the whole `git diff HEAD` again.
2.1. Run E0's steps 4, 6 and 7 again: the CI triggers, the standards sources and the verification commands are read from the repository, not remembered.
3. Rebuild: the commits on the branch (`git log origin/<default-branch>..HEAD`, each epic commit carries `Epic: {slug}`), the epics in `done/`, the pending `- [ ]` items, the `Pending decision (critical)` lines, and the pull request description (order, decisions, findings, CI).
4. The user's answer to a pending decision becomes a `DA-###` (user) that replaces the pending line; without an answer in the request, ask that question before calling the spike.
5. The order of the remaining epics comes from the pull request description when there is one; otherwise apply E1 again to the remaining epics. When there is no pull request yet (push CI), what the description needs from the epics committed earlier — decisions, deviations, non-blocking findings and Spec findings — comes from their commit bodies (E3.5), read with `git log`.
6. A ready pull request with every epic committed means the run is at the checkpoint: wait for the comment round or the approval.

---

## Execution-mode token economy

- **The spike is given the review's rules up front**: the standards sources and the CI's commands go in every call, and the spike returns a `DONE` only after checking its own work against them. A finding the gate sends back costs a spike round and a review; the same check inside the spike costs a few steps.
- **Each spike call carries only its slice**: at most 3 phases, the `DA-###` that bear on them, this run's answers, and a handoff or a fix request. Never the run's history, never another epic. You set the slice; the `HANDOFF` is only the safety valve.
- **Work that follows from a call continues that agent** (`SendMessage`): answers, review fix rounds and polish do not pay for a cold start.
- **Blocked questions are batched**: one `BLOCKED` block may carry several questions, and they go to the specialists in one round.
- **One full review per epic**, not per phase or slice. Every later gate is a delta gate: the open findings plus what changed since the snapshot, and the Spec sub-agent only when there are Spec items to confirm. Arbitration is one call per specialist, no counter-argument.
- **Findings come by class**: the gate lists every occurrence of a violated rule, and the fix request asks for a sweep, so the same rule does not come back at another location in the next gate.
- **Non-blocking findings are fixed before the commit**, in one polish round, instead of travelling to the pull request and coming back as a comment round.
- **Each call runs on the model its work needs** (see "Models").
- **Hard limits**: 1 counter-argument per question, 2 fix rounds per epic for the review and 2 for CI, 1 polish round per commit, 1 re-run per CI failure, 12 agent calls per session before the pause at an epic boundary.

---

## Internal run state

Track internally (no need to expose it to the user every turn):

- The scope, the order and its source; the branch, the CI triggers, the standards sources, the verification commands and the pull request number
- Per epic: its status (pending / in progress / committed / green), its slices and their `DONE` summaries, the id of the spike agent to continue, its commits, its review and CI fix-round counters and whether its polish round was used
- The open findings of the current gate (F and N numbers) and the deviations the architect accepted
- The next `Q` number, every answer and `DA-###` of the run (provisional ones flagged), the non-blocking findings still open and the CI results — everything the pull request description needs
- The number of `Agent` and `SendMessage` calls made in this session

## What NOT to do

- Do not enter execution mode without an explicit request to implement
- Do not write product code yourself — the spike implements; you write git history, the pull request and the epics' `DA-###` and pending decisions
- Do not let the spike commit, push or stage — every commit is yours, one per epic plus the fix commits, and the index is your gate snapshot
- Do not paste the `/spike` command's file into a spike call, nor send a slice larger than 3 phases or 12 items
- Do not start a new spike for a review or polish round when the agent that did the work can be continued
- Do not run a full review where a delta gate applies, nor let a late finding block
- Do not open more than one pull request per run, nor one per epic
- Do not force-push, merge, delete the branch or resolve a review thread
- Do not ask the user anything outside a stop (critical question, third failure, git/GitHub failure) — the order, the non-critical decisions and the review outcome go into the pull request
- Do not run `code-review` or `design-an-interface` inside the spike — they spawn sub-agents and run in this session
- Do not exceed 2 fix rounds per epic for the review or for CI, 1 polish round per commit, nor re-run a CI failure more than once
- Do not apply a pull request comment that contradicts a project standard without flagging it in the thread first
- Do not poll the pull request — the user tells you when there is something to read
- Do not go past the session budget, nor start a run or a comment round in a session that already carries other work

## Context control — MANDATORY

The pause is decided by the count in E3.7, never by an impression of how heavy the session is. At an epic boundary with 12 or more agent calls made in this session, stop there — never in the middle of an epic — and show:

> ⚠️ **This session has reached its budget.** Everything up to `{slug}` is committed and pushed on `{branch}`. Start a new session and ask `/flow` to resume the implementation: it picks up from the epics' checklists, the `flow/*` branch and the open pull request.

A run that fits in the budget goes straight to the pull request without this pause.
