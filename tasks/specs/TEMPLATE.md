# <Spec ID>: <title>

| Field | Value |
|---|---|
| Spec ID | S-<AREA>-<NN> |
| Issue | #<N> (batch: #<N>, #<N>) |
| Wave | W<N> |
| Role | coding |
| Status | READY |
| Size | S / M |
| Assigned executor | agent-run (overnight) |
| Base commit | <SHA of origin/main when written> |
| Branch | `agent/<Spec ID>` |
| Depends on | none |
| Conflicts with | none |
| Files owned | path/to/file.py, path/to/other.py |
| Migrations | none |
| Runtime locks | none |
| Changed-file limit | 8 |
| Changed-line limit | 300 |
| Human needed | none |

## Goal

<One paragraph: the observable result. Link the issue, journey and feature.>

## Context and citations

<For each fact the executor needs: `path:start-end`, the quoted line, and the
constraint it sets. Cite only code on the Base commit. The executor reads
nothing else.>

## Change

<Numbered, exact steps. Before and after code for every non-trivial edit. No
open design choices. Name every file, symbol and signature.>

## Out of scope

<What the executor must not touch. List the neighbours that look tempting.>

## Verification

<Exact commands and the expected output. Include the repo checks the change
needs, such as `just openapi` or `uv run pytest <path> -q`. Do not list a new
test unless the testing policy calls for one.>

## Done when

<The observable result and the checks that must pass. Merge the PR and set
Status to MERGED in the same commit.>
