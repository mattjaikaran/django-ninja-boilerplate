# Specs

A spec is a scoped unit of work that an unattended agent can finish without a
design decision. A frontier model writes the spec in a supervised planning
session. agent-run claims it overnight, implements it with a small model,
opens the PR, and matt-reviewer reviews that PR before the owner looks at it.
The full flow is in [../../docs/AGENT_HANDOFF.md](../../docs/AGENT_HANDOFF.md).

The spec file is the source of truth. A GitHub issue carries the same title
and links back to it; the issue is not the plan.

## Format

One file per spec: `tasks/specs/S-<AREA>-<NN>-<slug>.md`, where the ID is
`S-<AREA>-<NN>` and the file name starts with the ID. Use an uppercase area
code: `AUTH`, `API`, `TODOS`, `ORG`, `NOTIFY`, `BILL`, `FILES`, `HOOKS`,
`ADMIN`, `INFRA`, `DOCS` or `TEST`.

Start from [TEMPLATE.md](TEMPLATE.md). agent-run reads only the header table,
up to the first `## ` heading. Keep every row, and keep the keys spelled as
the template spells them.

|Key|Rule|
|---|---|
|`Spec ID`|`S-<AREA>-<NN>`. Must match the file name prefix.|
|`Issue`|One issue number, or a batch of issues.|
|`Wave`|`W0` to `W4`, from [../../docs/product/journeys.md](../../docs/product/journeys.md).|
|`Role`|`coding` for work agent-run may claim. Any other role is not claimed.|
|`Status`|`READY`, `BLOCKED-DEPS`, `BLOCKED-PLANNER`, `BLOCKED-HUMAN` or `MERGED`.|
|`Size`|`S` or `M`. An `L` issue is split before a spec is written.|
|`Assigned executor`|`agent-run (overnight)`, or the named executor.|
|`Base commit`|The `origin/main` SHA when the spec was written.|
|`Branch`|`agent/<Spec ID>`.|
|`Depends on`|Spec IDs that must be merged first, or `none`. agent-run checks this before claiming.|
|`Conflicts with`|Spec IDs that may not run at the same time, or `none`.|
|`Files owned`|Every path, directory or glob the diff may change. agent-run fails the gate on any other path.|
|`Migrations`|The app and purpose, or `none`. A listed migration is allowed outside `Files owned`.|
|`Runtime locks`|`none`, or the app stack the spec needs.|
|`Changed-file limit`|`8` for a component spec.|
|`Changed-line limit`|`300` for a component spec, lockfiles and generated files included in the count the gate prints.|
|`Human needed`|`none`, or the decision a human must make first.|

## Claim rules

A spec is claimable when:

- `Status` is `READY` and `Role` is `coding`.
- Every `Depends on` spec is `MERGED` or has a merged `agent/<ID>` PR.
- `Files owned` is non-empty and does not overlap a spec that is claimed now.
- No open or merged PR has the spec's branch or a title that starts with
  `S-...:`.

A spec that needs a path outside `Files owned`, or a design choice, is a spec
gap. agent-run stops, releases the claim, and opens a `spec-gap` issue. The
planner fixes the spec; the executor never widens it.

## Sizes

|Size|Work|Who does it|
|---|---|---|
|S|Exact edits, no design choice, about 300 lines or fewer|Overnight agent (small model, for example Haiku or DeepSeek Flash)|
|M|Fixed design, several files, about 300 lines or fewer|Overnight agent (small model, for example Haiku or DeepSeek Flash)|
|L|Open design, a new service or a cross-cutting refactor|Supervised session with a frontier model, which splits it into S and M specs|

The same S/M/L table, with the issue and batch rules, is in
[CONTRIBUTING.md](../../.github/CONTRIBUTING.md#sizes).

## Batch specs

Several small issues in the same area and wave may share one batch spec. A
batch:

- names every issue in `Issue`;
- owns the union of all component paths in `Files owned`;
- has one commit per component issue;
- keeps the PR at 2,000 changed lines or fewer, excluding lockfiles and
  generated files;
- closes every issue in the batch.

## Tests

Follow the testing policy in [AGENTS.md](../../AGENTS.md#10-definition-of-done).
A spec that fixes a bug includes the regression test. A spec that changes a
public contract or a boundary includes that test. A spec that only moves
files or renames a symbol does not add a test. Do not add a test file that
repeats a journey smoke test or an API contract test.

## Status lifecycle

```
draft spec -> READY -> claimed (agent/<ID> branch and PR) -> MERGED
                    -> BLOCKED-DEPS (a dependency is not merged)
                    -> BLOCKED-PLANNER (a spec gap needs the planner)
                    -> BLOCKED-HUMAN (a decision is missing)
```

`claimed` is not a header value. It is the `agent/<ID>` branch. Merging the
PR lands the code and sets `Status` to `MERGED` in the same commit.

## Writing a spec

1. Read the issue, the code it touches, and
   [../../docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md).
2. Make every design decision. Name exact paths, symbols and function
   signatures. Cite current code as `path:start-end` with the quoted lines.
3. Set `Status: READY` only when the change needs no decision, no path
   outside `Files owned`, and lists `## Verification` commands with the
   expected output.
4. Commit the spec. agent-run claims it from `origin/main`.
