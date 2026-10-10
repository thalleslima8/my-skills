---
name: design-an-interface
description: Use when frontend work creates or changes the interface of a frontend module (a component's props, children, slots and events; a hook's or composable's arguments and return value; a client-side store's state and actions; a client API or data-fetching module's functions), or when the user asks to "design it twice" or compare interface options for a frontend module. Generates several radically different interfaces in parallel sub-agents, checked against the project's frontend standards, compares them and recommends one; the user picks before anything is implemented (under /flow's execution mode, /flow runs it, the architect picks and the analyst validates). Not for styling, markup or behavior changes behind an unchanged interface.
argument-hint: "[the module to design]"
license: MIT
metadata:
  upstream: "https://github.com/mattpocock/skills (skills/deprecated/design-an-interface; its successor is codebase-design/DESIGN-IT-TWICE.md)"
  upstream-commit: "f958fa17c1b6"
---

# Design an interface

Based on "Design It Twice" from _A Philosophy of Software Design_ (Ousterhout): your first idea is unlikely to be the best. Generate several radically different interfaces, compare them, then pick.

Here "interface" means everything a caller must know to use a frontend module correctly, not the visual UI. For a component that is its props, children or slots, emitted events or callbacks, ref or imperative handle, and whether it is controlled or uncontrolled. For a hook, composable or store it is the arguments, the returned shape, when it re-runs or notifies, and its error and loading states. For a client API or data-fetching module it is the functions, their inputs and results, caching, and error modes. Invariants, ordering constraints and required context (providers, setup) are part of the interface too.

**Design only.** This skill never implements. The user picks the interface, and implementation is a separate step.

## When it applies

Run it when a frontend change:

- creates a module that other code will use: an exported or shared component, a hook or composable, a store, a client API or data-fetching module;
- changes an existing module's interface: adds, removes or renames props, events, arguments or returned fields, or changes their meaning.

Skip it, and say in one line why, when:

- the change sits behind an unchanged interface: styling, markup, internal state, a bug fix that keeps the contract;
- the module is private to one parent and not exported (a one-off subcomponent);
- the interface was already decided and recorded (a `DA-###` in the epic, an ADR, a design the user approved earlier in this session): follow it instead of reopening it;
- the user says to skip it.

What counts as frontend comes from the project's `CLAUDE.md`. If it does not say, frontend is the code that runs in the browser or client app: components, views, pages, hooks, client state and client data access.

## Process

### 1. Gather requirements and standards

Before designing, find out:

- What problem does this module solve?
- Who are the callers: which views or components, which other modules, the tests?
- What are the key operations or states (loading, empty, error, disabled, selected, …)?
- What should be hidden inside, and what must be exposed?
- Constraints: accessibility, performance (re-renders, bundle size), server or client rendering, compatibility with existing callers.

Look facts up yourself instead of asking: read the callers, and two or three existing modules of the same kind in the codebase to learn the house pattern. Read the project's frontend rules: `CLAUDE.md`, and `docs/standards/` (the general file and the frontend one) if the project uses that convention, or wherever `CLAUDE.md` points. Every design must comply with them. Ask the user only for what the code and docs cannot tell you.

Then write the user a short framing of the problem: the requirements, the constraints any interface must meet, the frontend rules that bind it (cited by ID when the rules have IDs, e.g. `FE-012`), and a rough sketch of how a caller would use it. This is not a proposal, only a way to make the constraints concrete. Show it and go straight on to step 2; the user reads while the sub-agents work.

### 2. Generate designs in parallel

Spawn 3 or 4 general-purpose sub-agents in the same message, each called with `model: "sonnet"` unless the user asked for another model: the value is in the contrast between the designs, which the comparison step judges. Each gets the same technical brief (the module's purpose, the requirements, the callers' file paths, the existing modules of the same kind, the frontend rules that apply, and the domain terms from `GLOSSARY.md` if there is one) plus a **different constraint**:

- Agent 1: "Minimize the interface: as few props, arguments or returned fields as possible. Make the module decide everything it can."
- Agent 2: "Maximize flexibility through composition: children, slots, render props, compound components or a headless core, so callers can build cases you have not foreseen."
- Agent 3: "Optimize for the most common caller: the default use is a one-liner, and the rarer cases are still possible."
- Agent 4 (when the project has a clear house pattern or a UI library): "Follow the project's existing pattern and its UI library's idioms as closely as possible."

Each sub-agent outputs:

1. The interface: types or prop and argument signatures, events or callbacks, returned shape, invariants, required context, error, loading and empty states
2. A usage example from the main caller, and one from an unusual case
3. What the module hides internally
4. Who owns accessibility: which roles, labels, keyboard handling and focus management are built in, and which the caller must provide
5. Trade-offs, including any frontend rule it bends and why

Add to every prompt: "Do not edit any file. Do not invoke the design-an-interface skill or spawn other agents: produce your design directly. Under 400 words."

### 3. Present the designs

Show each design in turn, with its interface, usage examples and what it hides, so the user can absorb each one before the comparison. Drop a design that breaks a mandatory project rule, and say which rule it broke.

### 4. Compare

Compare the designs in prose, not tables, and spend the words where they differ most:

- **Interface simplicity**: fewer props and arguments, simpler types, easier to learn and use correctly.
- **Depth**: a small interface hiding a lot of behavior (good) versus a large interface over a thin implementation (avoid). A component that forwards most of its props to one child is shallow.
- **General-purpose versus specialized**: can it take the next use case without a change, without over-generalizing now?
- **Ease of correct use versus ease of misuse**: impossible states unrepresentable, sensible defaults, no ordering traps.
- **Accessibility**: does correct use give an accessible result by default?
- **Rendering cost**: does the shape force needless re-renders or state the caller has to manage?
- **Testability**: can the behavior be tested through the interface the way a user or caller would use it?
- **Fit with the codebase**: consistency with the project's existing modules and frontend rules.

Do not judge a design by how much work it would take to implement.

### 5. Recommend and let the user pick

Give your own recommendation: the strongest design and why. If parts of different designs combine well, propose the hybrid. Be opinionated, then let the user decide, for example "Which one fits your main use case? Anything from the others worth folding in?"

When the user picks, restate the chosen interface in one block, the signature plus one usage example, as the reference for implementation. If the choice is hard to reverse, surprising without context and a real trade-off, offer to record it as an ADR through the `domain-modeling` skill.

## Under /flow's execution mode

When `/flow` implements epics with no user in the loop, the implementer is the `spike` agent, a sub-agent that cannot spawn this skill's sub-agents. It stops and hands the module back to `/flow` (a `BLOCKED` block of kind `interface`), and `/flow` runs this skill in its own session with these overrides:

- **Step 1:** the framing goes into the architect's prompt instead of to the user. What the code and docs cannot answer goes to the architect and the analyst, never to the user.
- **Steps 2–4:** unchanged.
- **Step 5:** `/flow` gives no recommendation of its own. The **architect picks** one design or a stated hybrid, and the **analyst validates** it against the epic's use cases and states. An objection gets one counter-argument; if they still disagree, the architect's choice stands as a provisional decision, unless the question is critical under `/flow`'s criteria, in which case `/flow` stops and asks the user.
- **Recording:** the choice becomes a `DA-###` in the epic, and the restated interface goes back to the spike as the reference for implementation.

## Anti-patterns

- Sub-agents producing similar designs: enforce radical difference.
- Skipping the comparison: the value is in the contrast.
- Implementing anything: this skill is about the shape of the interface only.
- Ignoring the project's frontend rules, or designing against the house pattern without saying so.
- Running it for a change that does not touch an interface.

## Source

Adapted from Matt Pocock's `design-an-interface` skill ([mattpocock/skills](https://github.com/mattpocock/skills), MIT, Copyright (c) 2026 Matt Pocock), removed upstream on 2026-08-05 and absorbed into `codebase-design` as `DESIGN-IT-TWICE.md`. Two ideas from the successor are kept here: framing the problem before spawning sub-agents, and ending with an opinionated recommendation. The upstream license ships next to this file.
