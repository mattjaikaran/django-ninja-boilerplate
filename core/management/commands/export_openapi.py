"""Export OpenAPI schema and generate SDK clients, Postman/Insomnia collections.

Provides a comprehensive command for:
- Exporting OpenAPI schema in JSON or YAML format
- Validating the OpenAPI specification
- Generating TypeScript and Python SDK clients
- Exporting Postman collections
- Exporting Insomnia collections
"""

import json
import sys
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.urls.base import resolve
from django.utils.module_loading import import_string


class Command(BaseCommand):
    help = "Export OpenAPI schema and optionally generate SDK clients and collections"

    def add_arguments(self, parser):
        # API selection
        parser.add_argument(
            "--api",
            type=str,
            default=None,
            help="Path to NinjaAPI instance (e.g., api.urls.api)",
        )

        # Output options
        parser.add_argument(
            "--output",
            "-o",
            type=str,
            default="docs/openapi",
            help="Output directory for generated files (default: docs/openapi)",
        )

        parser.add_argument(
            "--format",
            "-f",
            choices=["json", "yaml", "both"],
            default="json",
            help="Output format for OpenAPI spec (default: json)",
        )

        parser.add_argument(
            "--indent",
            type=int,
            default=2,
            help="JSON indentation level (default: 2)",
        )

        # Generation options
        parser.add_argument(
            "--sdk",
            action="store_true",
            help="Generate SDK clients (TypeScript and Python)",
        )

        parser.add_argument(
            "--sdk-typescript",
            action="store_true",
            help="Generate TypeScript SDK client only",
        )

        parser.add_argument(
            "--sdk-python",
            action="store_true",
            help="Generate Python SDK client only",
        )

        parser.add_argument(
            "--postman",
            action="store_true",
            help="Export Postman collection",
        )

        parser.add_argument(
            "--insomnia",
            action="store_true",
            help="Export Insomnia collection",
        )

        parser.add_argument(
            "--all",
            action="store_true",
            help="Generate everything (schema, SDKs, Postman, Insomnia)",
        )

        # Validation
        parser.add_argument(
            "--validate",
            action="store_true",
            help="Validate the OpenAPI specification",
        )

        parser.add_argument(
            "--no-validate",
            action="store_true",
            help="Skip validation even if openapi-spec-validator is installed",
        )

    def handle(self, *args, **options):
        # Get API instance
        api = self._get_api_instance(options.get("api"))

        # Create output directory
        output_dir = Path(options["output"])
        output_dir.mkdir(parents=True, exist_ok=True)

        self.stdout.write("")
        self.stdout.write("=" * 60)
        self.stdout.write(self.style.SUCCESS("  OpenAPI Export Tool"))
        self.stdout.write("=" * 60)
        self.stdout.write(f"Output Directory: {output_dir}")
        self.stdout.write("")

        # Export OpenAPI schema
        schema = api.get_openapi_schema()
        api_title = schema.get("info", {}).get("title", "API")
        api_version = schema.get("info", {}).get("version", "1.0.0")

        self.stdout.write(f"API: {api_title} v{api_version}")
        self.stdout.write("")

        # Save schema
        spec_path = self._save_schema(schema, output_dir, options)

        # Validate if requested
        if options.get("validate") and not options.get("no_validate"):
            self._validate_schema(schema)

        # Determine what to generate
        generate_all = options.get("all")
        generate_sdk = options.get("sdk") or generate_all
        generate_sdk_ts = options.get("sdk_typescript")
        generate_sdk_py = options.get("sdk_python")
        generate_postman = options.get("postman") or generate_all
        generate_insomnia = options.get("insomnia") or generate_all

        # Generate SDKs
        if generate_sdk or generate_sdk_ts or generate_sdk_py:
            language = "all"
            if generate_sdk_ts and not generate_sdk_py:
                language = "typescript"
            elif generate_sdk_py and not generate_sdk_ts:
                language = "python"

            self._generate_sdk(spec_path, output_dir, language)

        # Export Postman collection
        if generate_postman:
            self._export_postman(spec_path, output_dir)

        # Export Insomnia collection
        if generate_insomnia:
            self._export_insomnia(spec_path, output_dir)

        self.stdout.write("")
        self.stdout.write("=" * 60)
        self.stdout.write(self.style.SUCCESS("  Export Complete!"))
        self.stdout.write("=" * 60)
        self.stdout.write(f"\nFiles saved to: {output_dir.absolute()}")
        self.stdout.write("")

    def _get_api_instance(self, api_path=None):
        """Get the NinjaAPI instance."""
        if api_path:
            try:
                api = import_string(api_path)
                return api
            except ImportError:
                raise CommandError(f"Could not import API from: {api_path}")

        # Try to resolve from /api/ URL
        try:
            resolved = resolve("/api/")
            return resolved.func.keywords["api"]
        except Exception:
            pass

        # Try common import paths
        common_paths = [
            "api.urls.api",
            "config.urls.api",
            "project.urls.api",
        ]

        for path in common_paths:
            try:
                api = import_string(path)
                return api
            except ImportError:
                continue

        raise CommandError(
            "Could not find NinjaAPI instance. "
            "Please specify it with --api, e.g., --api api.urls.api"
        )

    def _save_schema(self, schema, output_dir, options):
        """Save the OpenAPI schema to file(s)."""
        output_format = options.get("format", "json")
        indent = options.get("indent", 2)

        json_path = output_dir / "openapi.json"
        yaml_path = output_dir / "openapi.yaml"

        if output_format in ("json", "both"):
            with open(json_path, "w") as f:
                json.dump(schema, f, indent=indent, default=str)
            self.stdout.write(self.style.SUCCESS(f"  Exported: {json_path}"))

        if output_format in ("yaml", "both"):
            try:
                import yaml as yaml_lib  # type: ignore[import-untyped]

                with open(yaml_path, "w") as f:
                    yaml_lib.dump(
                        schema, f, default_flow_style=False, allow_unicode=True
                    )
                self.stdout.write(self.style.SUCCESS(f"  Exported: {yaml_path}"))
            except ImportError:
                if output_format == "yaml":
                    raise CommandError(
                        "PyYAML is required for YAML output. Install with: uv add pyyaml"
                    )
                self.stdout.write(
                    self.style.WARNING("  Skipping YAML export (PyYAML not installed)")
                )

        # Return the JSON path (primary format)
        return json_path if json_path.exists() else yaml_path

    def _validate_schema(self, schema):
        """Validate the OpenAPI schema."""
        try:
            from openapi_spec_validator import validate_spec
            from openapi_spec_validator.exceptions import OpenAPIValidationError

            self.stdout.write("")
            self.stdout.write("Validating OpenAPI specification...")

            try:
                validate_spec(schema)
                self.stdout.write(self.style.SUCCESS("  Validation passed!"))
            except OpenAPIValidationError as e:
                self.stdout.write(self.style.ERROR(f"  Validation failed: {e}"))

        except ImportError:
            self.stdout.write(
                self.style.WARNING(
                    "  Skipping validation (openapi-spec-validator not installed)"
                )
            )

    def _generate_sdk(self, spec_path, output_dir, language):
        """Generate SDK clients."""
        self.stdout.write("")
        self.stdout.write(f"Generating SDK clients ({language})...")

        try:
            # Add scripts directory to path
            scripts_dir = Path(settings.BASE_DIR) / "scripts"
            if str(scripts_dir) not in sys.path:
                sys.path.insert(0, str(scripts_dir))

            from openapi.generate_sdk import SDKGenerator

            sdk_output = output_dir / "sdk"
            generator = SDKGenerator(spec_path, sdk_output)

            if language in ("typescript", "all"):
                ts_path = generator.generate_typescript()
                self.stdout.write(self.style.SUCCESS(f"  TypeScript SDK: {ts_path}"))

            if language in ("python", "all"):
                py_path = generator.generate_python()
                self.stdout.write(self.style.SUCCESS(f"  Python SDK: {py_path}"))

        except ImportError as e:
            self.stdout.write(self.style.ERROR(f"  SDK generation failed: {e}"))

    def _export_postman(self, spec_path, output_dir):
        """Export Postman collection."""
        self.stdout.write("")
        self.stdout.write("Exporting Postman collection...")

        try:
            scripts_dir = Path(settings.BASE_DIR) / "scripts"
            if str(scripts_dir) not in sys.path:
                sys.path.insert(0, str(scripts_dir))

            from openapi.export_postman import PostmanExporter

            exporter = PostmanExporter(spec_path)
            output_path = output_dir / "postman_collection.json"
            exporter.save(output_path)

            self.stdout.write(
                self.style.SUCCESS(f"  Postman collection: {output_path}")
            )

        except ImportError as e:
            self.stdout.write(self.style.ERROR(f"  Postman export failed: {e}"))

    def _export_insomnia(self, spec_path, output_dir):
        """Export Insomnia collection."""
        self.stdout.write("")
        self.stdout.write("Exporting Insomnia collection...")

        try:
            scripts_dir = Path(settings.BASE_DIR) / "scripts"
            if str(scripts_dir) not in sys.path:
                sys.path.insert(0, str(scripts_dir))

            from openapi.export_insomnia import InsomniaExporter

            exporter = InsomniaExporter(spec_path)
            output_path = output_dir / "insomnia_collection.json"
            exporter.save(output_path)

            self.stdout.write(
                self.style.SUCCESS(f"  Insomnia collection: {output_path}")
            )

        except ImportError as e:
            self.stdout.write(self.style.ERROR(f"  Insomnia export failed: {e}"))
