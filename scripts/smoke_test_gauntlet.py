#!/usr/bin/env python3
"""Gauntlet smoke test — validates that convention checkers catch known violations.

Creates synthetic files with known violations, runs the checker, and verifies
each violation type is detected. This proves the gauntlet works.

Usage:
    python scripts/smoke_test_gauntlet.py
    python scripts/smoke_test_gauntlet.py --verbose

Exit: 0 = all checks validated, 1 = one or more checks failed to detect violations
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Each test case: (check_name, file_content, expected_violation_count)
TEST_CASES = [
    (
        "DRF_IMPORT",
        "controllers/bad_controller.py",
        """from rest_framework import serializers

class BadView(serializers.ModelSerializer):
    class Meta:
        model = None
        fields = "__all__"
""",
        1,
    ),
    (
        "RAW_SCHEMA",
        "schemas/bad_schema.py",
        """from ninja import Schema

class BadSchema(Schema):
    name: str
    class Config:
        from_attributes = True
""",
        2,  # import + class
    ),
    (
        "MODEL_SCHEMA",
        "schemas/bad_modelschema.py",
        """from ninja import ModelSchema

class BadThing(ModelSchema):
    class Meta:
        model = None
        fields = "__all__"
""",
        2,  # import + class
    ),
    (
        "ROUTER_USAGE",
        "controllers/bad_router.py",
        """from ninja import Router

router = Router()

@router.get("/items")
def list_items(request):
    pass
""",
        2,  # import + Router()
    ),
    (
        "DECORATOR_ORDER",
        "controllers/bad_order.py",
        """from ninja_extra import api_controller, http_get

@api_controller("/items", tags=["Items"])
class BadController:
    @handle_exceptions()
    @http_get("/")
    def list_items(self, request):
        return []
""",
        1,
    ),
    (
        "MISSING_DECORATOR",
        "controllers/bad_missing.py",
        """from ninja_extra import api_controller, http_post

@api_controller("/items", tags=["Items"])
class BadController:
    @http_post("/")
    def create_item(self, request):
        return 201, {}
""",
        1,
    ),
    (
        "UNSCOPED_QUERY",
        "controllers/bad_unscoped.py",
        """from ninja_extra import api_controller, http_get

@api_controller("/items", tags=["Items"])
class BadController:
    @http_get("/")
    def list_items(self, request):
        return Item.objects.all()
""",
        1,
    ),
    (
        "REDECLARED_FIELDS",
        "models/bad_model.py",
        """from django.db import models

class BadModel(SoftDeleteModel):
    id = models.UUIDField(primary_key=True)
    created_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict)
    name = models.CharField(max_length=255)
""",
        4,  # id, created_at, is_active, metadata
    ),
    (
        "PIP_USAGE",
        "bad_install.py",
        """pip install django-ninja
print("hello")
""",
        1,
    ),
    (
        "MOCKED_ORM",
        "tests/test_bad.py",
        """def test_something(mocker):
    mocker.patch("app.models.Item.objects.create", return_value=None)
""",
        1,
    ),
]


@dataclass
class SmokeResult:
    check_name: str
    expected: int
    actual: int
    passed: bool
    output: str = ""


@dataclass
class SmokeRunner:
    results: list[SmokeResult] = field(default_factory=list)
    verbose: bool = False

    def run(self) -> int:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            # Write the checker into the temp dir (modified to use tmp as root)
            checker_src = (
                PROJECT_ROOT / "scripts" / "check_conventions.py"
            ).read_text()
            checker_src = checker_src.replace(
                "PROJECT_ROOT = Path(__file__).resolve().parent.parent",
                f"PROJECT_ROOT = Path('{tmp}')",
            )
            checker_path = tmp / "checker.py"
            checker_path.write_text(checker_src)

            all_passed = True

            for check_name, file_rel, content, expected_count in TEST_CASES:
                # Create the file
                file_path = tmp / file_rel
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(content)

                # Run the checker
                result = subprocess.run(  # noqa: PLW1510 — exit 1 means violations (expected)
                    ["uv", "run", "python", str(checker_path)],
                    capture_output=True,
                    text=True,
                    cwd=PROJECT_ROOT,
                    timeout=30,
                )

                output = result.stdout
                # Count violations for this specific check
                actual_count = output.count(f"[{check_name}]")

                passed = actual_count >= expected_count
                if not passed:
                    all_passed = False

                smoke_result = SmokeResult(
                    check_name=check_name,
                    expected=expected_count,
                    actual=actual_count,
                    passed=passed,
                    output=output if self.verbose else "",
                )
                self.results.append(smoke_result)

                if self.verbose or not passed:
                    status = "PASS" if passed else "FAIL"
                    print(
                        f"  [{status}] {check_name}: "
                        f"expected >= {expected_count}, got {actual_count}"
                    )
                    if not passed:
                        print(f"    Output: {output[:300]}")

        return self._print_summary(all_passed)

    def _print_summary(self, all_passed: bool) -> int:
        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)
        print(f"\nSmoke test: {passed}/{total} checks validated")
        if not all_passed:
            failed = [r.check_name for r in self.results if not r.passed]
            print(f"FAILED: {', '.join(failed)}")
        return 0 if all_passed else 1


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Gauntlet smoke test")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    runner = SmokeRunner(verbose=args.verbose)
    return runner.run()


if __name__ == "__main__":
    sys.exit(main())
