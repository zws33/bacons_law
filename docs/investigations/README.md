# Investigations

> **AUTHORITY: everything in this directory is a record, never a rule.**
>
> These documents describe how a question was investigated and what was found. They contain
> hypotheses that were later falsified, framings that were revised, and analysis that was
> superseded — **that is what they are for.** Nothing here is binding on the code.
>
> **If you are an agent looking for what this project has decided, you are in the wrong
> directory.** Rules live in [`../../AGENTS.md`](../../AGENTS.md). Decisions live in
> [`../DECISIONS.md`](../DECISIONS.md). The round engine's contract lives in
> [`../ENGINE_CONFORMANCE.md`](../ENGINE_CONFORMANCE.md). Never cite a file from this directory
> as authority for a change.

## Why this directory exists

Two reasons, one of them learned the hard way.

**The showcase reason.** How a question got investigated — what we predicted, what we measured,
what surprised us — is more instructive than the answer. Recording it makes the reasoning
reusable and the conclusions auditable.

**The safety reason.** A document full of provisional reasoning is a hazard to agents, which
retrieve by keyword search and windowed reads rather than reading top to bottom. A superseded
claim retrieved without its caveat reads as current fact. The project has already been bitten by
this: [`000-system-design-case-study.md`](000-system-design-case-study.md) built three sections
on a premise that [ADR 018](../DECISIONS.md) later overturned, and marking it in place turned out
to be only partial protection — a marker 200 lines above a claim is invisible to `grep`.

**The directory name is the fix.** A path appears in every search result, every file listing, and
every citation. It is the only metadata guaranteed to survive retrieval. Anything filed here is
non-normative *by location*, whatever an individual paragraph happens to assert.

## Conventions

**Numbered files (`001-`, `002-`, …) are investigations** and follow the template below: a
question, pre-registered hypotheses, a method, results, findings.

**`000-system-design-case-study.md` is a design retrospective**, not an investigation, and
predates the series. It keeps the `000-` prefix so it sorts first and reads as part of the record.
It does not follow the template.

### Status lifecycle

Every document carries a status in its header block:

| Status | Meaning |
|---|---|
| `IN PROGRESS` | Being worked. Results may be absent or partial. Hypotheses unresolved. |
| `COMPLETE` | Question answered. Conclusions promoted out (see below). |
| `SUPERSEDED` | Later work overturned the findings. Header says what replaced it. |

Status changes in the header block, **never in the filename** — renaming breaks every inbound
link, which is the opposite of the goal.

### Hypotheses carry line-level status

Pre-registration only works if a falsified prediction can never be mistaken for a finding. Each
hypothesis is tagged inline so a bare `grep` hit is self-describing:

```
**H2 · UNRESOLVED** — <prediction>       ← before measurement
**H2 · FALSIFIED**  — <prediction>       ← after; the prediction text is NOT edited
```

The original wording is never rewritten to match the outcome. A prediction that was wrong is the
most valuable line in the document.

### Conclusions get promoted out

**This is the rule that keeps the directory honest.** When an investigation completes, anything
binding moves to an ADR, `AGENTS.md`, or a spec, and the investigation links forward to where it
landed. Investigations hold evidence and reasoning; they must never become the place a future
reader learns a rule.

Without this, `docs/investigations/` slowly turns into a shadow specification — which is the
exact failure it was created to prevent, just with better intentions.

## Index

| Document | Status | Question |
|---|---|---|
| [000 — System design case study](000-system-design-case-study.md) | `SUPERSEDED IN PART` | How should the game be architected? (§2, §5, §6 overturned by [ADR 018](../DECISIONS.md)) |
| [001 — Actor degree distribution](001-actor-degree-distribution.md) | `COMPLETE` | How often does the graph offer a cheap round-ending move? → Rarely. No action on the data; cap rescue rejected ([ADR 019](../DECISIONS.md)) |
