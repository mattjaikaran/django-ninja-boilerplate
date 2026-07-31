---
name: codebase-design
description: Design deep modules — small interfaces, large implementations. Use when designing new modules, placing seams, making code testable, or improving architecture.
---

# Codebase Design — Deep Modules

Design **deep modules**: a lot of behavior behind a small interface, placed at a clean seam, testable through that interface.

## This repo's seams

| Layer | Seam | Interface | Implementation |
|-------|------|-----------|----------------|
| Controller | `@api_controller` class | Method signatures + response schemas | Delegates to service |
| Service | `CRUDService[Model]` | `create()`, `update()`, `delete()`, `list()` | Business logic, validation |
| Model | Django ORM | Fields, relationships, Meta | Database schema |
| Schema | Pydantic Schema | Field types, validators | Serialization, validation |

## Principles

- **Depth is at the interface, not the implementation.** A deep service has many internal methods but only a few public ones
- **The deletion test.** Delete the module — if complexity vanishes, it was a pass-through. If it spreads, it was earning its keep.
- **One adapter = hypothetical seam. Two adapters = real one.** Don't introduce a seam unless something varies across it.
- **Accept dependencies, don't create them.** Service takes dependencies in `__init__`, doesn't import them inline.
- **Return results, don't produce side effects.** Methods return values, callers decide what to do with them.

## Deep vs Shallow

**Deep** (good): `TodoService.create_todo(payload, user) → Todo` — small interface, complex validation + creation logic hidden inside.

**Shallow** (bad): `TodoService.create_todo_simple()`, `create_todo_with_tags()`, `create_todo_with_due_date()` — many methods, each thin. One method with optional params is better.

## When to deepen

- Same params appear in 3+ places → bundle into a type
- Controller has >5 lines of logic → extract to service method
- Service method >50 lines → split into private helpers behind the same public interface
- Multiple services share validation logic → extract to a shared validator module
