# .context/ — LLM Prompt Templates

This directory contains structured context files that enable any LLM (Claude, GPT, Cursor, Copilot, etc.) to correctly build features within this Django Ninja boilerplate.

## Files

| File | Purpose | When to Use |
|------|---------|-------------|
| **SYSTEM_PROMPT.md** | Complete system prompt with all rules, templates, and patterns | Feed to any LLM as system context before asking it to write code |
| **EXAMPLES.md** | Full vertical-slice examples (Notes, Projects+Tasks, Celery) | Reference when building a new feature — copy the closest example |
| **ANTI_PATTERNS.md** | Common LLM mistakes and how to fix them | Feed alongside SYSTEM_PROMPT to prevent DRF/function-view errors |
| **CONVENTIONS.md** | Naming, imports, file organization, code style | Reference for style questions |
| **PROMPTS.md** | Copy-paste prompts for common tasks | Quick task prompts (add endpoint, model, tests, etc.) |
| **PROJECT.md** | High-level project overview and tech stack | First read for understanding the codebase |

## Quick Start for LLM Integration

### Claude Code / CLAUDE.md
The root `CLAUDE.md` already references these patterns. Claude Code automatically reads it.

### Cursor
The `.cursor/rules/backend_guidelines.mdc` file covers the basics. For deeper context, paste `SYSTEM_PROMPT.md` into your Cursor rules or chat context.

### ChatGPT / Other LLMs
1. Copy `SYSTEM_PROMPT.md` as the system prompt
2. Optionally include `ANTI_PATTERNS.md` to prevent common mistakes
3. Reference `EXAMPLES.md` for the specific feature type you're building

### One-Liner for Any LLM

```
Read .context/SYSTEM_PROMPT.md and .context/ANTI_PATTERNS.md, then build [your feature description] following the patterns in .context/EXAMPLES.md.
```

## Philosophy

This boilerplate uses **Django Ninja Extra** (not DRF, not vanilla Django Ninja). Every feature follows a 5-layer vertical slice:

```
Model → Schema → Service → Controller → Tests
```

The context files exist because LLMs frequently default to DRF patterns (serializers, viewsets) since those dominate training data. These files correct that bias and enforce the actual architecture.
