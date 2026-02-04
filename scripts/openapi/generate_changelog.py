#!/usr/bin/env python
"""Generate API Changelog from OpenAPI Specifications.

This script compares two OpenAPI specification files and generates a changelog
documenting the differences between API versions.

Usage:
    python scripts/openapi/generate_changelog.py old.json new.json
    python scripts/openapi/generate_changelog.py old.json new.json -o changelog.md
    python scripts/openapi/generate_changelog.py old.json new.json --format json
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path


class ChangeType(Enum):
    """Types of API changes."""

    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    DEPRECATED = "deprecated"


class BreakingChange(Enum):
    """Breaking change classification."""

    BREAKING = "breaking"
    NON_BREAKING = "non-breaking"
    POSSIBLY_BREAKING = "possibly-breaking"


@dataclass
class Change:
    """Represents a single API change."""

    change_type: ChangeType
    breaking: BreakingChange
    path: str
    method: str | None
    description: str
    details: dict = field(default_factory=dict)


@dataclass
class Changelog:
    """Represents the complete changelog between two API versions."""

    old_version: str
    new_version: str
    generated_at: str
    summary: dict
    changes: list[Change]


# =============================================================================
# Changelog Generator
# =============================================================================


class ChangelogGenerator:
    """Generate changelog by comparing two OpenAPI specifications."""

    def __init__(self, old_spec_path: Path, new_spec_path: Path) -> None:
        """Initialize the changelog generator."""
        with open(old_spec_path) as f:
            self.old_spec = json.load(f)

        with open(new_spec_path) as f:
            self.new_spec = json.load(f)

        self.old_version = self.old_spec.get("info", {}).get("version", "unknown")
        self.new_version = self.new_spec.get("info", {}).get("version", "unknown")

        self.changes: list[Change] = []

    def generate(self) -> Changelog:
        """Generate the changelog."""
        # Compare paths/endpoints
        self._compare_paths()

        # Compare schemas
        self._compare_schemas()

        # Compare security definitions
        self._compare_security()

        # Compare info
        self._compare_info()

        # Generate summary
        summary = {
            "total_changes": len(self.changes),
            "breaking_changes": len(
                [c for c in self.changes if c.breaking == BreakingChange.BREAKING]
            ),
            "added": len([c for c in self.changes if c.change_type == ChangeType.ADDED]),
            "removed": len(
                [c for c in self.changes if c.change_type == ChangeType.REMOVED]
            ),
            "modified": len(
                [c for c in self.changes if c.change_type == ChangeType.MODIFIED]
            ),
            "deprecated": len(
                [c for c in self.changes if c.change_type == ChangeType.DEPRECATED]
            ),
        }

        return Changelog(
            old_version=self.old_version,
            new_version=self.new_version,
            generated_at=datetime.now().isoformat(),
            summary=summary,
            changes=self.changes,
        )

    def _compare_paths(self) -> None:
        """Compare API paths/endpoints."""
        old_paths = self.old_spec.get("paths", {})
        new_paths = self.new_spec.get("paths", {})

        old_path_set = set(old_paths.keys())
        new_path_set = set(new_paths.keys())

        # Added paths
        for path in new_path_set - old_path_set:
            methods = [
                m
                for m in new_paths[path]
                if m in ("get", "post", "put", "patch", "delete")
            ]
            for method in methods:
                self.changes.append(
                    Change(
                        change_type=ChangeType.ADDED,
                        breaking=BreakingChange.NON_BREAKING,
                        path=path,
                        method=method.upper(),
                        description=f"New endpoint: {method.upper()} {path}",
                        details={"operation": new_paths[path][method]},
                    )
                )

        # Removed paths
        for path in old_path_set - new_path_set:
            methods = [
                m
                for m in old_paths[path]
                if m in ("get", "post", "put", "patch", "delete")
            ]
            for method in methods:
                self.changes.append(
                    Change(
                        change_type=ChangeType.REMOVED,
                        breaking=BreakingChange.BREAKING,
                        path=path,
                        method=method.upper(),
                        description=f"Removed endpoint: {method.upper()} {path}",
                        details={"operation": old_paths[path][method]},
                    )
                )

        # Modified paths
        for path in old_path_set & new_path_set:
            self._compare_path_item(path, old_paths[path], new_paths[path])

    def _compare_path_item(
        self, path: str, old_item: dict, new_item: dict
    ) -> None:
        """Compare a single path item."""
        methods = {"get", "post", "put", "patch", "delete", "head", "options"}

        old_methods = set(old_item.keys()) & methods
        new_methods = set(new_item.keys()) & methods

        # Added methods
        for method in new_methods - old_methods:
            self.changes.append(
                Change(
                    change_type=ChangeType.ADDED,
                    breaking=BreakingChange.NON_BREAKING,
                    path=path,
                    method=method.upper(),
                    description=f"New method added: {method.upper()} {path}",
                    details={"operation": new_item[method]},
                )
            )

        # Removed methods
        for method in old_methods - new_methods:
            self.changes.append(
                Change(
                    change_type=ChangeType.REMOVED,
                    breaking=BreakingChange.BREAKING,
                    path=path,
                    method=method.upper(),
                    description=f"Method removed: {method.upper()} {path}",
                    details={"operation": old_item[method]},
                )
            )

        # Modified methods
        for method in old_methods & new_methods:
            self._compare_operation(path, method, old_item[method], new_item[method])

    def _compare_operation(
        self, path: str, method: str, old_op: dict, new_op: dict
    ) -> None:
        """Compare a single operation."""
        # Check for deprecation
        if not old_op.get("deprecated") and new_op.get("deprecated"):
            self.changes.append(
                Change(
                    change_type=ChangeType.DEPRECATED,
                    breaking=BreakingChange.NON_BREAKING,
                    path=path,
                    method=method.upper(),
                    description=f"Endpoint deprecated: {method.upper()} {path}",
                )
            )

        # Compare parameters
        self._compare_parameters(path, method, old_op, new_op)

        # Compare request body
        self._compare_request_body(path, method, old_op, new_op)

        # Compare responses
        self._compare_responses(path, method, old_op, new_op)

    def _compare_parameters(
        self, path: str, method: str, old_op: dict, new_op: dict
    ) -> None:
        """Compare operation parameters."""
        old_params = {p["name"]: p for p in old_op.get("parameters", [])}
        new_params = {p["name"]: p for p in new_op.get("parameters", [])}

        old_param_names = set(old_params.keys())
        new_param_names = set(new_params.keys())

        # Added required parameters (breaking)
        for name in new_param_names - old_param_names:
            param = new_params[name]
            if param.get("required"):
                self.changes.append(
                    Change(
                        change_type=ChangeType.ADDED,
                        breaking=BreakingChange.BREAKING,
                        path=path,
                        method=method.upper(),
                        description=f"New required parameter: {name}",
                        details={"parameter": param},
                    )
                )
            else:
                self.changes.append(
                    Change(
                        change_type=ChangeType.ADDED,
                        breaking=BreakingChange.NON_BREAKING,
                        path=path,
                        method=method.upper(),
                        description=f"New optional parameter: {name}",
                        details={"parameter": param},
                    )
                )

        # Removed parameters (breaking if required)
        for name in old_param_names - new_param_names:
            param = old_params[name]
            self.changes.append(
                Change(
                    change_type=ChangeType.REMOVED,
                    breaking=BreakingChange.BREAKING
                    if param.get("required")
                    else BreakingChange.NON_BREAKING,
                    path=path,
                    method=method.upper(),
                    description=f"Parameter removed: {name}",
                    details={"parameter": param},
                )
            )

        # Modified parameters
        for name in old_param_names & new_param_names:
            old_param = old_params[name]
            new_param = new_params[name]

            # Check if parameter became required
            if not old_param.get("required") and new_param.get("required"):
                self.changes.append(
                    Change(
                        change_type=ChangeType.MODIFIED,
                        breaking=BreakingChange.BREAKING,
                        path=path,
                        method=method.upper(),
                        description=f"Parameter '{name}' is now required",
                        details={"old": old_param, "new": new_param},
                    )
                )

            # Check type changes
            old_type = old_param.get("schema", {}).get("type")
            new_type = new_param.get("schema", {}).get("type")
            if old_type != new_type:
                self.changes.append(
                    Change(
                        change_type=ChangeType.MODIFIED,
                        breaking=BreakingChange.BREAKING,
                        path=path,
                        method=method.upper(),
                        description=f"Parameter '{name}' type changed from {old_type} to {new_type}",
                        details={"old": old_param, "new": new_param},
                    )
                )

    def _compare_request_body(
        self, path: str, method: str, old_op: dict, new_op: dict
    ) -> None:
        """Compare request body."""
        old_body = old_op.get("requestBody")
        new_body = new_op.get("requestBody")

        if not old_body and new_body and new_body.get("required"):
            self.changes.append(
                Change(
                    change_type=ChangeType.ADDED,
                    breaking=BreakingChange.BREAKING,
                    path=path,
                    method=method.upper(),
                    description="Required request body added",
                    details={"requestBody": new_body},
                )
            )
        elif old_body and not new_body:
            self.changes.append(
                Change(
                    change_type=ChangeType.REMOVED,
                    breaking=BreakingChange.POSSIBLY_BREAKING,
                    path=path,
                    method=method.upper(),
                    description="Request body removed",
                    details={"requestBody": old_body},
                )
            )

    def _compare_responses(
        self, path: str, method: str, old_op: dict, new_op: dict
    ) -> None:
        """Compare responses."""
        old_responses = old_op.get("responses", {})
        new_responses = new_op.get("responses", {})

        old_codes = set(old_responses.keys())
        new_codes = set(new_responses.keys())

        # Removed success responses are breaking
        for code in old_codes - new_codes:
            if code.startswith("2"):
                self.changes.append(
                    Change(
                        change_type=ChangeType.REMOVED,
                        breaking=BreakingChange.BREAKING,
                        path=path,
                        method=method.upper(),
                        description=f"Response {code} removed",
                        details={"response": old_responses[code]},
                    )
                )

        # Added responses
        for code in new_codes - old_codes:
            self.changes.append(
                Change(
                    change_type=ChangeType.ADDED,
                    breaking=BreakingChange.NON_BREAKING,
                    path=path,
                    method=method.upper(),
                    description=f"New response {code} added",
                    details={"response": new_responses[code]},
                )
            )

    def _compare_schemas(self) -> None:
        """Compare component schemas."""
        old_schemas = self.old_spec.get("components", {}).get("schemas", {})
        new_schemas = self.new_spec.get("components", {}).get("schemas", {})

        old_schema_names = set(old_schemas.keys())
        new_schema_names = set(new_schemas.keys())

        # Added schemas
        for name in new_schema_names - old_schema_names:
            self.changes.append(
                Change(
                    change_type=ChangeType.ADDED,
                    breaking=BreakingChange.NON_BREAKING,
                    path=f"#/components/schemas/{name}",
                    method=None,
                    description=f"New schema added: {name}",
                    details={"schema": new_schemas[name]},
                )
            )

        # Removed schemas
        for name in old_schema_names - new_schema_names:
            self.changes.append(
                Change(
                    change_type=ChangeType.REMOVED,
                    breaking=BreakingChange.POSSIBLY_BREAKING,
                    path=f"#/components/schemas/{name}",
                    method=None,
                    description=f"Schema removed: {name}",
                    details={"schema": old_schemas[name]},
                )
            )

        # Modified schemas
        for name in old_schema_names & new_schema_names:
            old_schema = old_schemas[name]
            new_schema = new_schemas[name]

            if old_schema != new_schema:
                self._compare_schema_properties(name, old_schema, new_schema)

    def _compare_schema_properties(
        self, schema_name: str, old_schema: dict, new_schema: dict
    ) -> None:
        """Compare schema properties."""
        old_props = old_schema.get("properties", {})
        new_props = new_schema.get("properties", {})
        old_required = set(old_schema.get("required", []))
        new_required = set(new_schema.get("required", []))

        old_prop_names = set(old_props.keys())
        new_prop_names = set(new_props.keys())

        # Added required properties (breaking)
        for prop in new_prop_names - old_prop_names:
            if prop in new_required:
                self.changes.append(
                    Change(
                        change_type=ChangeType.ADDED,
                        breaking=BreakingChange.BREAKING,
                        path=f"#/components/schemas/{schema_name}",
                        method=None,
                        description=f"New required property '{prop}' added to schema {schema_name}",
                        details={"property": new_props[prop]},
                    )
                )

        # Removed properties (possibly breaking)
        for prop in old_prop_names - new_prop_names:
            self.changes.append(
                Change(
                    change_type=ChangeType.REMOVED,
                    breaking=BreakingChange.POSSIBLY_BREAKING,
                    path=f"#/components/schemas/{schema_name}",
                    method=None,
                    description=f"Property '{prop}' removed from schema {schema_name}",
                    details={"property": old_props[prop]},
                )
            )

        # Properties that became required
        for prop in (new_required - old_required) & old_prop_names:
            self.changes.append(
                Change(
                    change_type=ChangeType.MODIFIED,
                    breaking=BreakingChange.BREAKING,
                    path=f"#/components/schemas/{schema_name}",
                    method=None,
                    description=f"Property '{prop}' is now required in schema {schema_name}",
                )
            )

    def _compare_security(self) -> None:
        """Compare security definitions."""
        old_security = self.old_spec.get("components", {}).get("securitySchemes", {})
        new_security = self.new_spec.get("components", {}).get("securitySchemes", {})

        if old_security != new_security:
            self.changes.append(
                Change(
                    change_type=ChangeType.MODIFIED,
                    breaking=BreakingChange.POSSIBLY_BREAKING,
                    path="#/components/securitySchemes",
                    method=None,
                    description="Security schemes modified",
                    details={"old": old_security, "new": new_security},
                )
            )

    def _compare_info(self) -> None:
        """Compare API info."""
        old_info = self.old_spec.get("info", {})
        new_info = self.new_spec.get("info", {})

        if old_info.get("title") != new_info.get("title"):
            self.changes.append(
                Change(
                    change_type=ChangeType.MODIFIED,
                    breaking=BreakingChange.NON_BREAKING,
                    path="#/info/title",
                    method=None,
                    description=f"API title changed from '{old_info.get('title')}' to '{new_info.get('title')}'",
                )
            )


# =============================================================================
# Output Formatters
# =============================================================================


def format_markdown(changelog: Changelog) -> str:
    """Format changelog as Markdown."""
    lines = [
        "# API Changelog",
        "",
        f"## {changelog.old_version} -> {changelog.new_version}",
        "",
        f"Generated: {changelog.generated_at}",
        "",
        "### Summary",
        "",
        f"- **Total Changes:** {changelog.summary['total_changes']}",
        f"- **Breaking Changes:** {changelog.summary['breaking_changes']}",
        f"- **Added:** {changelog.summary['added']}",
        f"- **Removed:** {changelog.summary['removed']}",
        f"- **Modified:** {changelog.summary['modified']}",
        f"- **Deprecated:** {changelog.summary['deprecated']}",
        "",
    ]

    # Group changes by breaking status
    breaking_changes = [c for c in changelog.changes if c.breaking == BreakingChange.BREAKING]
    possibly_breaking = [c for c in changelog.changes if c.breaking == BreakingChange.POSSIBLY_BREAKING]
    non_breaking = [c for c in changelog.changes if c.breaking == BreakingChange.NON_BREAKING]

    if breaking_changes:
        lines.extend([
            "### Breaking Changes",
            "",
        ])
        for change in breaking_changes:
            method_str = f"{change.method} " if change.method else ""
            lines.append(f"- **{change.change_type.value.upper()}** {method_str}{change.path}")
            lines.append(f"  - {change.description}")
        lines.append("")

    if possibly_breaking:
        lines.extend([
            "### Possibly Breaking Changes",
            "",
        ])
        for change in possibly_breaking:
            method_str = f"{change.method} " if change.method else ""
            lines.append(f"- **{change.change_type.value.upper()}** {method_str}{change.path}")
            lines.append(f"  - {change.description}")
        lines.append("")

    if non_breaking:
        lines.extend([
            "### Non-Breaking Changes",
            "",
        ])
        for change in non_breaking:
            method_str = f"{change.method} " if change.method else ""
            lines.append(f"- **{change.change_type.value.upper()}** {method_str}{change.path}")
            lines.append(f"  - {change.description}")
        lines.append("")

    return "\n".join(lines)


def format_json(changelog: Changelog) -> str:
    """Format changelog as JSON."""
    data = {
        "old_version": changelog.old_version,
        "new_version": changelog.new_version,
        "generated_at": changelog.generated_at,
        "summary": changelog.summary,
        "changes": [
            {
                "type": c.change_type.value,
                "breaking": c.breaking.value,
                "path": c.path,
                "method": c.method,
                "description": c.description,
                "details": c.details,
            }
            for c in changelog.changes
        ],
    }
    return json.dumps(data, indent=2)


# =============================================================================
# Main
# =============================================================================


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate API changelog from OpenAPI specifications",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/openapi/generate_changelog.py old.json new.json
    python scripts/openapi/generate_changelog.py old.json new.json -o changelog.md
    python scripts/openapi/generate_changelog.py old.json new.json --format json
        """,
    )

    parser.add_argument(
        "old_spec",
        type=Path,
        help="Path to the old OpenAPI specification file",
    )

    parser.add_argument(
        "new_spec",
        type=Path,
        help="Path to the new OpenAPI specification file",
    )

    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Output file path (default: stdout)",
    )

    parser.add_argument(
        "--format",
        "-f",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)",
    )

    args = parser.parse_args()

    # Validate input files
    if not args.old_spec.exists():
        print(f"Error: Old spec file not found: {args.old_spec}")
        sys.exit(1)

    if not args.new_spec.exists():
        print(f"Error: New spec file not found: {args.new_spec}")
        sys.exit(1)

    # Generate changelog
    generator = ChangelogGenerator(args.old_spec, args.new_spec)
    changelog = generator.generate()

    # Format output
    if args.format == "json":
        output = format_json(changelog)
    else:
        output = format_markdown(changelog)

    # Write output
    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Changelog written to: {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
