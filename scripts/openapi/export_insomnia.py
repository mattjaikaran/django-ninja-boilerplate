#!/usr/bin/env python
"""Export Insomnia Collection from OpenAPI Specification.

This script converts an OpenAPI specification to Insomnia v4 export format.

Usage:
    python scripts/openapi/export_insomnia.py openapi.json
    python scripts/openapi/export_insomnia.py openapi.json -o insomnia_collection.json
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

# =============================================================================
# Insomnia Exporter
# =============================================================================


def generate_id(prefix: str = "req") -> str:
    """Generate a unique ID for Insomnia resources."""
    import hashlib
    import time

    unique = f"{time.time()}-{id(object())}"
    hash_val = hashlib.md5(unique.encode()).hexdigest()[:24]
    return f"{prefix}_{hash_val}"


class InsomniaExporter:
    """Export OpenAPI specification to Insomnia export format."""

    def __init__(self, spec_path: Path) -> None:
        """Initialize the Insomnia exporter."""
        self.spec_path = spec_path

        with open(spec_path) as f:
            self.spec = json.load(f)

        self.api_title = self.spec.get("info", {}).get("title", "API")
        self.api_version = self.spec.get("info", {}).get("version", "1.0.0")
        self.api_description = self.spec.get("info", {}).get("description", "")

        # Get base URL
        servers = self.spec.get("servers", [])
        self.base_url = servers[0].get("url", "http://localhost:8000/api") if servers else "http://localhost:8000/api"

        # IDs for resources
        self.workspace_id = generate_id("wrk")
        self.env_id = generate_id("env")
        self.base_env_id = generate_id("env")

    def export(self) -> dict:
        """Export to Insomnia export format."""
        resources = []

        # Create workspace
        workspace = {
            "_id": self.workspace_id,
            "_type": "workspace",
            "name": self.api_title,
            "description": self.api_description,
            "scope": "collection",
            "created": int(datetime.now().timestamp() * 1000),
            "modified": int(datetime.now().timestamp() * 1000),
        }
        resources.append(workspace)

        # Create base environment
        base_env = {
            "_id": self.base_env_id,
            "_type": "environment",
            "name": "Base Environment",
            "data": {},
            "dataPropertyOrder": None,
            "color": None,
            "isPrivate": False,
            "metaSortKey": 1,
            "parentId": self.workspace_id,
            "created": int(datetime.now().timestamp() * 1000),
            "modified": int(datetime.now().timestamp() * 1000),
        }
        resources.append(base_env)

        # Create environment with variables
        environment = {
            "_id": self.env_id,
            "_type": "environment",
            "name": "Development",
            "data": {
                "base_url": self.base_url,
                "auth_token": "",
            },
            "dataPropertyOrder": {"&": ["base_url", "auth_token"]},
            "color": "#7d69cb",
            "isPrivate": False,
            "metaSortKey": 1,
            "parentId": self.base_env_id,
            "created": int(datetime.now().timestamp() * 1000),
            "modified": int(datetime.now().timestamp() * 1000),
        }
        resources.append(environment)

        # Group endpoints by tags
        endpoints_by_tag: dict[str, list] = {}

        for path, path_item in self.spec.get("paths", {}).items():
            for method, operation in path_item.items():
                if method not in ("get", "post", "put", "patch", "delete", "head", "options"):
                    continue

                tags = operation.get("tags", ["Default"])
                for tag in tags:
                    if tag not in endpoints_by_tag:
                        endpoints_by_tag[tag] = []
                    endpoints_by_tag[tag].append((path, method, operation))

        # Create folders for each tag
        sort_key = 0
        for tag, endpoints in endpoints_by_tag.items():
            # Create folder
            folder_id = generate_id("fld")
            folder = {
                "_id": folder_id,
                "_type": "request_group",
                "name": tag,
                "description": self._get_tag_description(tag),
                "environment": {},
                "environmentPropertyOrder": None,
                "metaSortKey": sort_key,
                "parentId": self.workspace_id,
                "created": int(datetime.now().timestamp() * 1000),
                "modified": int(datetime.now().timestamp() * 1000),
            }
            resources.append(folder)
            sort_key += 1000

            # Create requests in folder
            for request_sort_key, (path, method, operation) in enumerate(endpoints):
                request = self._create_request(
                    path, method, operation, folder_id, request_sort_key
                )
                resources.append(request)

        return {
            "_type": "export",
            "__export_format": 4,
            "__export_date": datetime.now().isoformat(),
            "__export_source": "openapi-exporter",
            "resources": resources,
        }

    def _get_tag_description(self, tag: str) -> str:
        """Get description for a tag from OpenAPI spec."""
        tags = self.spec.get("tags", [])
        for t in tags:
            if t.get("name") == tag:
                return t.get("description", "")
        return ""

    def _create_request(
        self, path: str, method: str, operation: dict, parent_id: str, sort_key: int
    ) -> dict:
        """Create an Insomnia request from an OpenAPI operation."""
        operation_id = operation.get("operationId", f"{method}_{path}")
        summary = operation.get("summary", operation_id)
        description = operation.get("description", "")

        # Build URL with path parameters
        url = "{{ _.base_url }}" + path
        for param in operation.get("parameters", []):
            if param["in"] == "path":
                url = url.replace(f"{{{param['name']}}}", f"{{{{ _.{param['name']} }}}}")

        # Build query parameters
        parameters = []
        for param in operation.get("parameters", []):
            if param["in"] == "query":
                parameters.append(
                    {
                        "id": generate_id("pair"),
                        "name": param["name"],
                        "value": self._get_example_value(param.get("schema", {})),
                        "description": param.get("description", ""),
                        "disabled": not param.get("required", False),
                    }
                )

        # Build headers
        headers = []
        for param in operation.get("parameters", []):
            if param["in"] == "header":
                headers.append(
                    {
                        "id": generate_id("pair"),
                        "name": param["name"],
                        "value": self._get_example_value(param.get("schema", {})),
                        "description": param.get("description", ""),
                    }
                )

        # Add Content-Type for requests with body
        request_body = operation.get("requestBody", {})
        body = {}

        if request_body:
            content = request_body.get("content", {})

            if "application/json" in content:
                json_content = content["application/json"]
                schema = json_content.get("schema", {})
                example = json_content.get("example") or self._generate_example(schema)

                body = {
                    "mimeType": "application/json",
                    "text": json.dumps(example, indent=2),
                }

            elif "application/x-www-form-urlencoded" in content:
                form_content = content["application/x-www-form-urlencoded"]
                schema = form_content.get("schema", {})
                properties = schema.get("properties", {})

                params = []
                for prop_name, prop_schema in properties.items():
                    params.append(
                        {
                            "id": generate_id("pair"),
                            "name": prop_name,
                            "value": self._get_example_value(prop_schema),
                            "description": prop_schema.get("description", ""),
                        }
                    )

                body = {"mimeType": "application/x-www-form-urlencoded", "params": params}

            elif "multipart/form-data" in content:
                multipart_content = content["multipart/form-data"]
                schema = multipart_content.get("schema", {})
                properties = schema.get("properties", {})

                params = []
                for prop_name, prop_schema in properties.items():
                    param = {
                        "id": generate_id("pair"),
                        "name": prop_name,
                        "description": prop_schema.get("description", ""),
                    }

                    if prop_schema.get("format") == "binary":
                        param["type"] = "file"
                        param["fileName"] = ""
                    else:
                        param["type"] = "text"
                        param["value"] = self._get_example_value(prop_schema)

                    params.append(param)

                body = {"mimeType": "multipart/form-data", "params": params}

        # Determine authentication
        authentication = {}
        security = operation.get("security", self.spec.get("security", []))
        if security:
            authentication = {
                "type": "bearer",
                "token": "{{ _.auth_token }}",
                "prefix": "Bearer",
            }

        request = {
            "_id": generate_id("req"),
            "_type": "request",
            "name": summary,
            "description": description,
            "method": method.upper(),
            "url": url,
            "body": body,
            "parameters": parameters,
            "headers": headers,
            "authentication": authentication,
            "metaSortKey": sort_key,
            "isPrivate": False,
            "settingStoreCookies": True,
            "settingSendCookies": True,
            "settingDisableRenderRequestBody": False,
            "settingEncodeUrl": True,
            "settingRebuildPath": True,
            "settingFollowRedirects": "global",
            "parentId": parent_id,
            "created": int(datetime.now().timestamp() * 1000),
            "modified": int(datetime.now().timestamp() * 1000),
        }

        return request

    def _get_example_value(self, schema: dict) -> str:
        """Get an example value for a schema."""
        if "example" in schema:
            return str(schema["example"])

        if "default" in schema:
            return str(schema["default"])

        schema_type = schema.get("type", "string")
        schema_format = schema.get("format", "")

        examples = {
            "string": {
                "": "string",
                "email": "user@example.com",
                "uri": "https://example.com",
                "uuid": "550e8400-e29b-41d4-a716-446655440000",
                "date": "2024-01-01",
                "date-time": "2024-01-01T00:00:00Z",
                "password": "password123",
            },
            "integer": {"": "0", "int32": "0", "int64": "0"},
            "number": {"": "0.0", "float": "0.0", "double": "0.0"},
            "boolean": {"": "true"},
            "array": {"": "[]"},
            "object": {"": "{}"},
        }

        type_examples = examples.get(schema_type, {"": ""})
        return type_examples.get(schema_format, type_examples.get("", ""))

    def _generate_example(self, schema: dict) -> dict | list | str | int | bool | None:
        """Generate an example value from a schema."""
        if "example" in schema:
            return schema["example"]

        if "$ref" in schema:
            ref_path = schema["$ref"].split("/")
            ref_schema = self.spec
            for part in ref_path[1:]:  # Skip the first '#'
                ref_schema = ref_schema.get(part, {})
            return self._generate_example(ref_schema)

        schema_type = schema.get("type", "object")

        if schema_type == "object":
            result = {}
            for prop_name, prop_schema in schema.get("properties", {}).items():
                result[prop_name] = self._generate_example(prop_schema)
            return result

        if schema_type == "array":
            items_schema = schema.get("items", {})
            return [self._generate_example(items_schema)]

        # Primitive types
        type_examples = {
            "string": "string",
            "integer": 0,
            "number": 0.0,
            "boolean": True,
        }

        return type_examples.get(schema_type)

    def save(self, output_path: Path) -> None:
        """Export and save the Insomnia collection."""
        collection = self.export()

        with open(output_path, "w") as f:
            json.dump(collection, f, indent=2)

        print(f"Exported Insomnia collection: {output_path}")


# =============================================================================
# Main
# =============================================================================


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Export Insomnia Collection from OpenAPI specification",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/openapi/export_insomnia.py openapi.json
    python scripts/openapi/export_insomnia.py openapi.json -o my_collection.json
        """,
    )

    parser.add_argument(
        "spec_path",
        type=Path,
        help="Path to OpenAPI specification file (JSON or YAML)",
    )

    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Output file path (default: <api_name>_insomnia.json)",
    )

    args = parser.parse_args()

    # Validate input file
    if not args.spec_path.exists():
        print(f"Error: OpenAPI spec file not found: {args.spec_path}")
        sys.exit(1)

    # Create exporter
    exporter = InsomniaExporter(args.spec_path)

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        safe_name = re.sub(r"[^a-zA-Z0-9]+", "_", exporter.api_title.lower())
        output_path = args.spec_path.parent / f"{safe_name}_insomnia.json"

    print("=" * 60)
    print("Insomnia Collection Exporter")
    print("=" * 60)
    print(f"Input:  {args.spec_path}")
    print(f"Output: {output_path}")
    print(f"API:    {exporter.api_title} v{exporter.api_version}")
    print("=" * 60)

    # Export
    exporter.save(output_path)

    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)
    print("\nImport in Insomnia: Application -> Preferences -> Data -> Import Data")
    print(f"                    Or drag and drop {output_path}")


if __name__ == "__main__":
    main()
