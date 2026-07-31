---
name: grill-me
description: Relentless interview to sharpen a plan or design before implementation. Use when user wants to stress-test thinking or uses "grill me" trigger phrases.
disable-model-invocation: true
---

Interview the user relentlessly about every aspect of the plan until shared understanding is reached. Walk down each branch of the decision tree, resolving dependencies between decisions one-by-one.

For each question, provide your **recommended answer** based on this repo's conventions.

Ask questions **one at a time**, waiting for feedback on each before continuing. Multiple questions at once is bewildering.

If a *fact* can be found by exploring the environment (filesystem, code, configs), look it up rather than asking. The *decisions* are the user's — put each one and wait.

## What to grill on

- **Scope**: What exactly is being built? What's explicitly NOT being built?
- **Architecture**: Which layer? Controller → Service → Model? New app or existing?
- **Schema**: What does the API contract look like? CamelCase input/output?
- **Auth**: Who can access this? JWT? API key? Public?
- **Testing**: What seams to test at? Integration or unit?
- **Edge cases**: What happens when it fails? Rate limited? Empty result?
- **Dependencies**: Does this need new packages? (Default: NO — use what's here)

## This repo's defaults (use when recommending)

- Framework: Django Ninja Extra (NOT DRF)
- Schemas: CamelCaseSchema from core.schemas.base_schema
- Controllers: @api_controller class-based, thin HTTP adapters
- Services: CRUDService[Model], business logic only
- Models: SoftDeleteModel default
- Testing: pytest + Factory Boy, real database, no mocks
- Package manager: uv, NEVER pip

Do not act until user confirms shared understanding.
