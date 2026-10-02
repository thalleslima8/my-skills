---
name: grill-me
description: A relentless interview that turns a loose idea, plan or decision into a shared understanding, asked in rounds of numbered questions with a recommended answer each. Inside a repository it also builds the project's domain model (GLOSSARY.md, ADRs) through the domain-modeling skill; outside one (or with "no-docs") it writes nothing. Use ONLY when the user types /grill-me or asks to be grilled, or when a command such as /flow tells you to run it. Never start it on your own otherwise.
argument-hint: "[docs | no-docs] [topic]"
license: MIT
metadata:
  upstream: "https://github.com/mattpocock/skills (grill-me, grill-with-docs, grilling)"
  upstream-commit: "d81f3a183412"
---

# Grill me

Interview the user relentlessly until you both reach a shared understanding of their idea. The idea can be anything: a feature, a product direction, a business call, a piece of writing. It does not need to be worked out yet. Producing a worked-out version is what the session is for.

This session asks; it does not build. Change no code and produce no spec or epic while the interview is running. The only files you may write are the glossary and ADRs of **docs mode**.

## Pick the mode first

- **Docs mode**: the session runs inside a repository (there is a `.git`, or a project `CLAUDE.md`) and the subject is that project. The interview also builds the project's domain model, following the `domain-modeling` skill.
- **Plain mode**: no repository, or the subject has nothing to do with the project (a business call, a piece of writing, a personal decision). Stateless: nothing is written anywhere.

The argument overrides the detection: `docs` forces docs mode, `no-docs` forces plain mode. Otherwise decide on your own and say in one line at the top of the first round which mode you picked, so the user can switch (e.g. "Docs mode: I'll record terms in GLOSSARY.md as they settle. Say no-docs to keep this session file-free.").

In docs mode, before the first round, read the project's `CLAUDE.md`, the existing `GLOSSARY.md` (or `GLOSSARY-MAP.md`) and the titles of the existing ADRs.

## Language

Ask in the language the user is writing in. Keep the format markers below (`❓`, `➡️`, `Q1`) as they are.

## The design tree

Map the idea as a **design tree**: every decision branches into the decisions that hang off it.

Work the tree in **rounds**. The **frontier** is every decision whose prerequisites are already settled: the questions you can ask *now* without guessing at answers you haven't heard yet. Ask the whole frontier in one round, number each question and give your recommended answer. Then wait for the user's answers before the next round.

If the user's `CLAUDE.md` (global or project) says to ask one question at a time, do that instead: one question per message, still with a recommended answer, still taken from the frontier.

Format a round like so:

```
❓ **Q1** - **<question title>**: <question body, might be multiple paragraphs, including multiple choices>

➡️ <your recommended answer>

---

❓ **Q2** - **<question title>**: <question body, might be multiple paragraphs, including multiple choices>

➡️ <your recommended answer>
```

Each round the user answers reshapes the tree: settled decisions push the frontier outward and unblock the questions that depended on them. Recompute the frontier and ask the next round. A question whose answer depends on another question still open in this round belongs to a *later* round, not this one.

Recommend, don't rubber-stamp. A recommended answer is your actual opinion, and when the user's answer looks wrong (it contradicts an earlier answer, ignores an edge case, or rests on a fact that isn't true), say so once, briefly, and let them decide. "I don't know" is a valid answer: record the decision as open and keep going with the rest of the tree.

## Facts are your job, decisions are the user's

Never ask the user for a fact you can look up yourself. When a frontier question needs a fact from the environment (the codebase, the project's `CLAUDE.md`, docs, existing epics, tools), dispatch a sub-agent (e.g. `Explore`) to find it. Don't block on it: a running lookup is an unsettled prerequisite, so only the questions downstream of it wait for the sub-agent to report; ask the rest of the frontier now.

The *decisions* belong to the user. Put each one to them and wait.

## Docs mode: build the domain model as you go

Skip this section in plain mode. Otherwise apply the `domain-modeling` skill for the whole session:

- Challenges to the language (a term that conflicts with the glossary, a fuzzy word, an edge-case scenario, a claim the code contradicts) become questions in the next round.
- A resolved term is written to the glossary in the same turn, and the change is mentioned in one line at the top of the next round.
- An ADR candidate (hard to reverse, surprising, a real trade-off) is offered as a question in the next round, with your recommendation, and written only on a yes.

Everything else the user decided lives only in this conversation. That is why the hand-off at the end happens in the same conversation.

## Ungrillable questions

Some questions can't be settled by talking: "one long form or three pages?", "how should this interaction feel?". They need something to react to. When you hit one, don't keep rephrasing it. Mark it as needing a throwaway prototype (in a code project, a `/spike` session can build one), move on with the rest of the tree, and let the user come back with a one-line answer.

## Scope

If the tree keeps growing round after round, the scope is probably too big for one session. Say so, propose how to split it into smaller pieces, and let the user pick the piece to grill first.

## Ending the session

The session is done when the frontier is empty: every branch of the tree visited, nothing left silently assumed. Then:

1. Summarize the shared understanding in one compact list: each decision with the answer the user gave, plus anything left open or waiting on a prototype. In docs mode, also list the glossary terms added or changed and the ADRs written.
2. Ask the user to confirm the summary. Do not act on it until they do.
3. Only after confirmation, offer the next step without taking it. In a project that uses the `workflow` plugin, the natural hand-off is `/flow` (or `/analyst`) to turn the decisions into an epic, in this same conversation so the context you built carries over. Never commit the glossary or ADRs yourself.

## When another command runs it

A command can run this skill as its engine. Then the calling command's rules win where they differ, including **who answers the rounds**. `/flow` is the main case: it keeps the design tree, the frontier and the rounds, but puts each round to its architect and analyst agents instead of the user, cross-checks their answers, and only brings the user the conflicts and the decisions that are theirs alone. In that mode:

- The answering agents' replies replace your recommended answer; you do not recommend anything yourself.
- "Facts are your job" still holds: look facts up instead of asking anyone for them.
- At the end, do not offer a next step: hand the result back to the calling command and continue with its next step.

## Source

Adapted from Matt Pocock's `grill-me`, `grill-with-docs` and `grilling` skills ([mattpocock/skills](https://github.com/mattpocock/skills), MIT, Copyright (c) 2026 Matt Pocock), merged into one skill. The domain-modeling half lives in this plugin's `domain-modeling` skill so other commands can use it too. The upstream license ships next to this file.
