---
name: loop-me
description: Grill the user, over as many sessions as it takes, into workflow specs an implementer agent could build without asking a single question, using the current directory as a stateful workspace (workflows/*.md and NOTES.md). Use ONLY when the user types /loop-me. Never start it on your own.
disable-model-invocation: true
argument-hint: "[a workflow to design, or nothing to go find one]"
license: MIT
metadata:
  upstream: "https://github.com/mattpocock/skills (skills/in-progress/loop-me)"
  upstream-commit: "d81f3a183412"
---

# Loop me

Run a stateful grilling session whose only output is **workflow** specs. Use the `grill-me` skill's discipline: the design tree, a round of numbered questions at a time over the whole frontier, a recommended answer on each, facts looked up instead of asked, decisions left to the user. Aim it at the vocabulary and goal below. Create, edit and delete specs as the grilling resolves things.

This skill replaces `grill-me`'s modes: there is no docs or plain mode here. The only files this session writes are the workspace files below, never the project's `GLOSSARY.md`, ADRs or code.

## The loop lens

A **loop** is a recurring pattern in the user's life: their career, their week, their morning, a single repeated activity. Picturing a life as loops within loops shows how predictable its activities really are, which is what makes them worth **delegating**. Use the lens to find loops worth specifying, and propose ones the user hasn't noticed.

A **workflow** is the spec of one loop, made real. You run a workflow on a loop: the loop is its running instantiation. Workflows live in `workflows/*.md` and are the source of truth.

## Vocabulary

A shared language, reached for only when a workflow calls for it: never a checklist. **Mandate nothing structural**: a workflow needs no AI, no checkpoint and no schedule unless the grilling shows it does.

- **Trigger**: what fires each run, an **event** (a new email, a new issue) or a **schedule** (every morning). Event triggers are usually the more efficient.
- **Checkpoint**: a human-in-the-loop point where the user is asked to verify or decide. Some workflows have none and run autonomously; some use no AI at all.
- **Push right**: defer the checkpoint as far as it will go. Do the most work possible before involving the human, so they are asked once, late, with everything prepared.
- **Brief**: what a checkpoint presents, a tight, decision-ready summary (what was produced, why, and a link down to the asset itself), never the raw output. The user reads a brief, not a draft. Speed of review is what matters.

## Definition of done

A workflow spec is done when an implementer agent could build it without asking a single question. Grill until then; nothing is done while a question remains. A question left open (an "I don't know", or one waiting on a prototype) stays written in the spec as open, so the next session picks it up.

## The workspace

The current directory is the workspace:

- `workflows/*.md`: one spec per workflow, named after the loop in `kebab-case`.
- `NOTES.md`: raw notes on the user's world, the tools they use, the channels they process, and their own terminology for both.

If neither exists yet, say which directory you are about to use and confirm it before creating anything: a code repository is rarely the right home for personal workflows. Write the files in the language the user is grilling in, unless the existing files already use another.

## Running a session

1. **Read the state.** Read `NOTES.md` and every spec in `workflows/`, and say in one line what you found: how many specs, which are done, which have open questions.
2. **Know the world first.** When `NOTES.md` is empty or thin, interview the user about their world (tools, channels, the recurring work they do) before specifying anything. Record what you learn in `NOTES.md` as it settles. Sharpen fuzzy terms into canonical ones as they surface, and record them there too.
3. **Pick the loop.** With an argument, grill that workflow (a new spec, or the existing one it names). With none, use the loop lens on `NOTES.md` and the existing specs: propose the loops that look most worth delegating, plus the specs with open questions, and let the user pick.
4. **Grill it.** Work the workflow's design tree in rounds, as `grill-me` does. Write each decision into the spec in the same turn it settles, and mention the change in one line at the top of the next round. Look facts up yourself (in the workspace, or the tools the user has connected) before asking for them.
5. **Delete only on a decision.** Remove or merge a spec only when the user decides to in a round, never on your own.
6. **End.** When the spec meets the definition of done, or the user stops, summarize what changed in the workspace this session and what is still open. Offer a next step without taking it. Never commit the workspace.

## Source

Adapted from Matt Pocock's `loop-me` skill ([mattpocock/skills](https://github.com/mattpocock/skills), MIT, Copyright (c) 2026 Matt Pocock), which is in that repository's beta (`in-progress`) bucket. The upstream license ships next to this file.
