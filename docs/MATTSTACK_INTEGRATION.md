# Mattstack-CLI Integration

How the four-layer gauntlet defense works alongside `mattstack audit`.

## Division of Labor

| Concern | Gauntlet (per-stack) | Mattstack Audit (cross-stack) |
|---------|---------------------|-------------------------------|
| **Type drift** | — | `TypeSafetyAuditor`: Pydantic ↔ TS ↔ Zod |
| **Endpoint coverage** | — | `EndpointAuditor`: duplicate routes, stubs, missing auth |
| **Code quality** | Convention checker (AST patterns) | `CodeQualityAuditor`: TODOs, stubs, credentials, debug |
| **Test coverage** | pytest/vitest gates | `CoverageAuditor`: missing test files, uncovered schemas |
| **Dependencies** | pip-audit gate | `DependencyAuditor`: unpinned, deprecated, cross-manifest |
| **Vulnerabilities** | — | `VulnerabilityAuditor`: CVEs via pip-audit + OSV.dev |
| **Convention violations** | `check_conventions.py` + `.omp/rules/` | — |
| **Architecture layers** | `check_architecture.py` | — |
| **File length** | `check_file_length.py` | — |
| **Framework identity** | TTSR rules + APPEND_SYSTEM.md | — |

## When to Use What

### Use the Gauntlet for:
- Every commit (`pre-commit` hooks)
- Every PR (`make gauntlet-quick` in CI)
- Catching AI anti-patterns (DRF imports, raw Schema, `as any`, `@ts-ignore`)
- Framework-specific conventions (decorator order, component patterns)
- Mid-generation interruption (TTSR rules)

### Use Mattstack Audit for:
- Cross-stack consistency checks (weekly or pre-release)
- Type drift detection between backend schemas and frontend types
- Dependency hygiene across pyproject.toml + package.json
- Security vulnerability scanning (CVEs)
- Generating actionable todo.md tasks

## Running Both

### In a Monorepo (backend/ + frontend/)

```bash
# Per-stack gauntlets
cd backend && make gauntlet-quick
cd frontend && bun run gauntlet:quick

# Cross-stack audit
mattstack audit --type types,endpoints,dependencies

# Full check
cd backend && make gauntlet-quick && \
cd ../frontend && bun run gauntlet:quick && \
cd .. && mattstack audit
```

### Combined CI Pipeline

```yaml
# .github/workflows/fullstack-gauntlet.yml
jobs:
  backend-gauntlet:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Backend Gauntlet
        run: cd backend && make gauntlet-ci

  frontend-gauntlet:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Frontend Gauntlet
        run: cd frontend && bun run gauntlet:quick

  cross-stack-audit:
    needs: [backend-gauntlet, frontend-gauntlet]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Mattstack Audit
        run: mattstack audit --type types,endpoints,dependencies --json
```

## The Combined Defense

```
                    ┌──────────────────────────────┐
                    │     Mattstack Audit          │
                    │  (cross-stack, periodic)     │
                    │  types | endpoints | deps    │
                    │  quality | tests | vulns     │
                    └──────────┬───────────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
  ┌───────▼────────┐  ┌───────▼────────┐  ┌───────▼────────┐
  │ Backend        │  │ Cross-Stack    │  │ Frontend       │
  │ Gauntlet       │  │ Checker        │  │ Gauntlet       │
  │ (12 gates)     │  │ (5 checks)     │  │ (6 gates)      │
  │                │  │                │  │                │
  │ format         │  │ naming         │  │ format         │
  │ lint           │  │ schema parity  │  │ lint:strict    │
  │ typecheck      │  │ tooling        │  │ type-check     │
  │ security       │  │ rules          │  │ test           │
  │ conventions    │  │ gauntlet       │  │ build          │
  │ cross-stack    │  │                │  │ conventions    │
  │ architecture   │  │                │  │                │
  │ filelength     │  │                │  │                │
  │ test           │  │                │  │                │
  │ mutation       │  │                │  │                │
  │ audit          │  │                │  │                │
  │ deploy-check   │  │                │  │                │
  └────────────────┘  └────────────────┘  └────────────────┘
          │                    │                    │
          └────────────────────┼────────────────────┘
                               │
                    ┌──────────▼───────────────────┐
                    │  4-Layer Defense (per stack) │
                    │  L1: System Prompt           │
                    │  L2: Always-Apply Rules      │
                    │  L3: TTSR Mid-Generation     │
                    │  L4: Deterministic Gates     │
                    └──────────────────────────────┘
```
