#!/usr/bin/env python3
"""Export gauntlet rules and tools as a portable bundle.

Creates a directory containing all convention enforcement artifacts
that can be dropped into any codebase — language and framework agnostic.

The exported bundle includes:
  - .omp/rules/          → always-apply and TTSR rules
  - .omp/APPEND_SYSTEM.md → system prompt guardrails
  - scripts/             → convention checker (framework-adaptable)

Usage:
    python scripts/export_rules.py                     # exports to ./gauntlet-export/
    python scripts/export_rules.py --output /tmp/rules  # custom output dir
    python scripts/export_rules.py --list               # list what would be exported
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

EXPORT_MANIFEST = [
    # (source, dest_rel, description)
    (
        ".omp/APPEND_SYSTEM.md",
        ".omp/APPEND_SYSTEM.md",
        "System prompt guardrails — injects anti-pattern rules into every session",
    ),
    (
        ".omp/rules/backend-conventions.md",
        ".omp/rules/backend-conventions.md",
        "Always-apply rule: framework identity, decorator order, naming, layer architecture",
    ),
    (
        ".omp/rules/django-ninja-anti-patterns.md",
        ".omp/rules/django-ninja-anti-patterns.md",
        "Always-apply rule: wrong vs. right code examples for 12 common AI mistakes",
    ),
    (
        ".omp/rules/ttsr-framework-identity.md",
        ".omp/rules/ttsr-framework-identity.md",
        "TTSR rule: interrupts when model generates DRF/raw Schema/Router/ModelSchema",
    ),
    (
        ".omp/rules/ttsr-convention-violations.md",
        ".omp/rules/ttsr-convention-violations.md",
        "TTSR rule: interrupts on wrong decorator order, redeclared fields",
    ),
    (
        ".omp/skills/engineering/code-review/SKILL.md",
        ".omp/skills/engineering/code-review/SKILL.md",
        "Code review skill: two-axis review (Standards + Spec) with Fowler smell baseline",
    ),
    (
        ".omp/skills/engineering/tdd/SKILL.md",
        ".omp/skills/engineering/tdd/SKILL.md",
        "TDD skill: red-green-refactor loop with seam-based testing",
    ),
    (
        ".omp/skills/engineering/implement/SKILL.md",
        ".omp/skills/engineering/implement/SKILL.md",
        "Implement skill: grill → TDD → typecheck → test → review → gauntlet",
    ),
    (
        ".omp/skills/engineering/codebase-design/SKILL.md",
        ".omp/skills/engineering/codebase-design/SKILL.md",
        "Codebase design skill: deep modules, seams, interfaces, testability",
    ),
    (
        ".omp/skills/productivity/grill-me/SKILL.md",
        ".omp/skills/productivity/grill-me/SKILL.md",
        "Grill-me skill: relentless interview to sharpen plans before coding",
    ),
    (
        "scripts/check_conventions.py",
        "scripts/check_conventions.py",
        "AST-based convention checker — 12 deterministic checks",
    ),
    (
        "scripts/gauntlet.py",
        "scripts/gauntlet.py",
        "Gauntlet orchestrator — chains all quality gates",
    ),
    (
        "scripts/check_architecture.py",
        "scripts/check_architecture.py",
        "Architecture layer enforcement checker",
    ),
    (
        "scripts/check_file_length.py",
        "scripts/check_file_length.py",
        "File length enforcement checker",
    ),
    (
        "CLAUDE.md",
        "CLAUDE.md",
        "AI agent conventions — gauntlet, architecture rules, definition of done",
    ),
    (
        ".context/CONVENTIONS.md",
        ".context/CONVENTIONS.md",
        "Coding conventions reference — naming, imports, error handling",
    ),
    (
        ".context/ANTI_PATTERNS.md",
        ".context/ANTI_PATTERNS.md",
        "Anti-patterns reference — full wrong/right examples",
    ),
    (
        ".context/SYSTEM_PROMPT.md",
        ".context/SYSTEM_PROMPT.md",
        "LLM system prompt template — identity, templates, layer contracts",
    ),
    (
        "docs/PORTABLE_GAUNTLET.md",
        "docs/PORTABLE_GAUNTLET.md",
        "How to adapt the gauntlet to any codebase",
    ),
    (
        "scripts/check_cross_stack.py",
        "scripts/check_cross_stack.py",
        "Cross-stack convention checker — naming, schema parity, tooling consistency",
    ),
    (
        "docs/MATTSTACK_INTEGRATION.md",
        "docs/MATTSTACK_INTEGRATION.md",
        "How the gauntlet integrates with mattstack-cli audit",
    ),
]


def export_rules(output_dir: Path, dry_run: bool = False) -> None:
    output_dir = Path(output_dir)

    if dry_run:
        print(f"Would export to: {output_dir}")
    else:
        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"Exporting to: {output_dir}")

    exported = 0
    missing = 0

    for src_rel, dest_rel, description in EXPORT_MANIFEST:
        src = PROJECT_ROOT / src_rel
        dest = output_dir / dest_rel

        if not src.exists():
            print(f"  SKIP (missing): {src_rel}")
            missing += 1
            continue

        if dry_run:
            print(f"  WOULD COPY: {src_rel} -> {dest_rel}")
            print(f"    {description}")
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            print(f"  COPY: {src_rel} -> {dest_rel}")
            print(f"    {description}")

        exported += 1

    # Create README in export
    if not dry_run:
        readme = output_dir / "README.md"
        readme.write_text(f"""# Gauntlet Export — Portable Convention Enforcement

Exported from django-ninja-boilerplate.

## What's in this bundle

{exported} files across 4 layers of defense:

### Layer 1: System Prompt Injection (`.omp/APPEND_SYSTEM.md`)
Injected into every AI session. Establishes non-negotiable guardrails.

### Layer 2: Always-Apply Rules (`.omp/rules/backend-*.md`)
Full convention reference injected into every system prompt.

### Layer 3: TTSR Mid-Generation Rules (`.omp/rules/ttsr-*.md`)
Interrupts the model mid-generation when it writes prohibited patterns.

### Layer 4: Deterministic Gauntlet Gates (`scripts/check_*.py`)
Post-generation verification — catches what the LLM ignored.

## Installation

Drop into your project root:
```bash
cp -r .omp/ $YOUR_PROJECT/
cp scripts/check_conventions.py $YOUR_PROJECT/scripts/
cp scripts/gauntlet.py $YOUR_PROJECT/scripts/
```

Adapt the convention checker to your framework — see `docs/PORTABLE_GAUNTLET.md`.

## Running

```bash
python scripts/check_conventions.py   # single gate
make gauntlet-quick                    # all gates
```
""")
        print(f"\n  Created: {readme}")

    print(f"\nExported {exported} files ({missing} missing).")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export gauntlet rules as portable bundle"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="gauntlet-export",
        help="Output directory (default: gauntlet-export/)",
    )
    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="List what would be exported (dry run)",
    )
    args = parser.parse_args()

    export_rules(args.output, dry_run=args.list)
    return 0


if __name__ == "__main__":
    sys.exit(main())
