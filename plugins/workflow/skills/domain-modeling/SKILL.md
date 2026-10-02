---
name: domain-modeling
description: Use when a session is shaping a project's domain language or recording a lasting decision — challenging or defining project terms, writing or editing GLOSSARY.md (or GLOSSARY-MAP.md), or recording an ADR for a decision that is hard to reverse, surprising and a real trade-off. Applies inside /grill-me, /arquiteto, /flow, /analyst or any other session. Merely reading GLOSSARY.md for vocabulary does not need this skill.
license: MIT
metadata:
  upstream: "https://github.com/mattpocock/skills (skills/engineering/domain-modeling)"
  upstream-commit: "d81f3a183412"
---

# Domain modeling

Actively build and sharpen the project's domain model while a design is being discussed: challenge terms, invent edge-case scenarios, and write the glossary and the decisions down the moment they settle. This is the *active* discipline. Reading `GLOSSARY.md` to use the right words is a habit any session should have; this skill is for when the model is being *changed*.

## Where things live

Defaults, unless the project's `CLAUDE.md` names other locations (then the project wins):

```
/
├── GLOSSARY.md
├── docs/
│   └── adr/
│       ├── 0001-event-sourced-orders.md
│       └── 0002-postgres-for-write-model.md
└── src/
```

If a `GLOSSARY-MAP.md` exists at the root, the repo has several contexts and the map points to each one's glossary; context-specific ADRs live next to that glossary, system-wide ones in the root `docs/adr/`. See [GLOSSARY-FORMAT.md](GLOSSARY-FORMAT.md).

Create files lazily: no `GLOSSARY.md` until the first term is resolved, no ADR directory until the first ADR is accepted.

Files follow the language of the project's existing docs; with none, the language the project's `CLAUDE.md` declares, then English.

## Who writes

Only a session allowed to write documentation writes these files (e.g. `/grill-me` in docs mode, `/arquiteto`, `/flow`, `/spike`). A read-only persona (`/analyst`, the `analyst` and `arquiteto` agents) still challenges terms and spots ADR candidates, but hands them back as proposals ("term to record", "ADR candidate") instead of writing. Never commit these files: committing is the user's call.

## While the discussion runs

### Challenge against the glossary

When someone uses a term that conflicts with `GLOSSARY.md`, call it out right away: "Your glossary defines 'cancellation' as X, but you seem to mean Y. Which is it?"

### Sharpen fuzzy language

When a term is vague or overloaded, propose a precise canonical one: "You're saying 'account': do you mean the Customer or the User? Those are different things."

### Discuss concrete scenarios

When relationships between concepts are being discussed, stress-test them with specific scenarios that probe the edges and force the boundary between concepts to be stated.

### Cross-reference with code

When someone states how something works, check whether the code agrees (directly, or through a sub-agent when the session must stay lean or may not read code). Surface any contradiction: "Your code cancels entire Orders, but you just said partial cancellation is possible. Which is right?"

### Update GLOSSARY.md inline

When a term is resolved, update the glossary right there, in the same turn. Don't batch terms up for the end. Use the format in [GLOSSARY-FORMAT.md](GLOSSARY-FORMAT.md), and tell the user in one line what changed.

`GLOSSARY.md` is a glossary and nothing else: no implementation details, no spec, no scratch notes, no general programming concepts. If a sentence describes *how* the system does something, it does not belong there.

### Offer ADRs sparingly

Offer an ADR only when all three are true:

1. **Hard to reverse**: changing your mind later has a real cost.
2. **Surprising without context**: a future reader will wonder "why did they do it this way?"
3. **The result of a real trade-off**: there were genuine alternatives and one was picked for specific reasons.

If any of the three is missing, skip it. Most discussions produce no ADR, and that is fine. Ask before writing one, and write it only on a yes, using [ADR-FORMAT.md](ADR-FORMAT.md).

### ADRs and `DA-###` decisions

`/arquiteto` and `/flow` record a session's decisions as `DA-###` inside the design doc or epic. Those are working records tied to one piece of work. An ADR is the durable, repo-wide record, and only the `DA-###` decisions that pass the three gates above become one. When that happens, write the ADR and link the two both ways (the `DA-###` entry points to the ADR file, the ADR mentions the `DA-###` and the epic it came from).

## Source

Adapted from the `domain-modeling` skill of Matt Pocock's [mattpocock/skills](https://github.com/mattpocock/skills) (MIT, Copyright (c) 2026 Matt Pocock). Changed: the project's `CLAUDE.md` can name other locations, a "who writes" rule for read-only personas, a never-commit rule, and how ADRs relate to `/arquiteto` and `/flow`'s `DA-###` decisions. `GLOSSARY-FORMAT.md` and `ADR-FORMAT.md` are upstream's, with the location override added. The upstream license ships next to this file.
