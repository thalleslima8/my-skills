---
name: ef-migrations
description: Use whenever a model change in a .NET/EF Core project generates a migration (dotnet ef migrations add) — the migration must be applied to the local database in the same turn, never left pending. Triggers automatically during implementation or bug fixing in .NET projects using EF Core, regardless of which command or agent is active.
---

# EF Core migrations — always apply in the same turn

> **This rule has no exceptions: every migration created is applied to the local database in the same turn it was generated.**

Whenever a model change requires `dotnet ef migrations add <Name>`, run the following right after, before continuing the implementation:

```bash
dotnet ef database update \
  --project <path to the infrastructure/persistence project> \
  --startup-project <path to the startup project>
```

Adjust `--project` and `--startup-project` to the real projects declared in the current project's CLAUDE.md — names vary per product.

The local database must never fall behind the migrations generated during the implementation — that breaks the next integration test and the next local startup for whoever picks up the branch.

If `database update` fails because the local database is down, report the error and point to the local infrastructure declared by the project (e.g. `docker compose up -d`, if the project uses containers) before proceeding — **do not keep implementing with an outdated schema.**
