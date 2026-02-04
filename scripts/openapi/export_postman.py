#!/usr/bin/env python
"""Export Postman Collection from OpenAPI Specification.

This script converts an OpenAPI specification to a Postman Collection v2.1 format.

Usage:
    python scripts/openapi/export_postman.py openapi.json
    python scripts/openapi/export_postman.py openapi.json -o postman_collection.json
"""

import argparse
import json
import re
import sys
import uuid
from pathlib import Path

# =============================================================================
# Postman Collection Generator
# =============================================================================


class PostmanExporter:
    """Export OpenAPI specification to Postman Collection format."""

    def __init__(self, spec_path: Path) -> None:
        """Initialize the Postman exporter."""
        self.spec_path = spec_path

        with open(spec_path) as f:
            self.spec = json.load(f)

        self.api_title = self.spec.get("info", {}).get("title", "API")
        self.api_version = self.spec.get("info", {}).get("version", "1.0.0")
        self.api_description = self.spec.get("info", {}).get("description", "")

    def export(self) -> dict:
        """Export to Postman Collection format."""
        collection = {
            "info": {
                "_postman_id": str(uuid.uuid4()),
                "name": self.api_title,
                "description": self.api_description,
                "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
                "_exporter_id": "openapi-exporter",
            },
            "item": [],
            "event": [],
            "variable": self._generate_variables(),
        }

        # Group endpoints by tags
        endpoints_by_tag: dict[str, list] = {}

        for path, path_item in self.spec.get("paths", {}).items():
            for method, operation in path_item.items():
                if method not in (
                    "get",
                    "post",
                    "put",
                    "patch",
                    "delete",
                    "head",
                    "options",
                ):
                    continue

                tags = operation.get("tags", ["Default"])
                request_item = self._create_request_item(path, method, operation)

                for tag in tags:
                    if tag not in endpoints_by_tag:
                        endpoints_by_tag[tag] = []
                    endpoints_by_tag[tag].append(request_item)

        # Create folders for each tag
        for tag, items in endpoints_by_tag.items():
            folder = {
                "name": tag,
                "item": items,
                "description": self._get_tag_description(tag),
            }
            collection["item"].append(folder)

        # Add authentication setup
        collection["auth"] = {
            "type": "bearer",
            "bearer": [{"key": "token", "value": "{{auth_token}}", "type": "string"}],
        }

        return collection

    def _generate_variables(self) -> list[dict]:
        """Generate Postman collection variables."""
        # Get base URL from servers
        servers = self.spec.get("servers", [])
        base_url = "http://localhost:8000/api"

        if servers:
            base_url = servers[0].get("url", base_url)

        return [
            {
                "key": "base_url",
                "value": base_url,
                "type": "string",
                "description": "API base URL",
            },
            {
                "key": "auth_token",
                "value": "",
                "type": "string",
                "description": "JWT authentication token",
            },
        ]

    def _get_tag_description(self, tag: str) -> str:
        """Get description for a tag from OpenAPI spec."""
        tags = self.spec.get("tags", [])
        for t in tags:
            if t.get("name") == tag:
                return t.get("description", "")
        return ""

    def _create_request_item(self, path: str, method: str, operation: dict) -> dict:
        """Create a Postman request item from an OpenAPI operation."""
        operation_id = operation.get("operationId", f"{method}_{path}")
        summary = operation.get("summary", operation_id)
        description = operation.get("description", "")

        # Build URL
        url = self._build_url(path, operation)

        # Build headers
        headers = self._build_headers(operation)

        # Build request body
        body = self._build_body(operation)

        request_item = {
            "name": summary,
            "request": {
                "method": method.upper(),
                "header": headers,
                "url": url,
                "description": description,
            },
            "response": self._build_example_responses(operation),
        }

        if body:
            request_item["request"]["body"] = body

        # Add authentication if required
        security = operation.get("security", self.spec.get("security", []))
        if security:
            request_item["request"]["auth"] = {
                "type": "bearer",
                "bearer": [
                    {"key": "token", "value": "{{auth_token}}", "type": "string"}
                ],
            }

        return request_item

    def _build_url(self, path: str, operation: dict) -> dict:
        """Build Postman URL object from path and parameters."""
        # Convert path parameters from {param} to :param format
        postman_path = re.sub(r"\{(\w+)\}", r":\1", path)

        # Parse path into parts
        path_parts = [p for p in postman_path.split("/") if p]

        url = {
            "raw": "{{base_url}}" + postman_path,
            "host": ["{{base_url}}"],
            "path": path_parts,
        }

        # Add query parameters
        query_params = []
        path_variables = []

        for param in operation.get("parameters", []):
            if param["in"] == "query":
                query_params.append(
                    {
                        "key": param["name"],
                        "value": self._get_example_value(param.get("schema", {})),
                        "description": param.get("description", ""),
                        "disabled": not param.get("required", False),
                    }
                )
            elif param["in"] == "path":
                path_variables.append(
                    {
                        "key": param["name"],
                        "value": self._get_example_value(param.get("schema", {})),
                        "description": param.get("description", ""),
                    }
                )

        if query_params:
            url["query"] = query_params

        if path_variables:
            url["variable"] = path_variables

        return url

    def _build_headers(self, operation: dict) -> list[dict]:
        """Build headers for the request."""
        headers = []

        # Check for header parameters
        for param in operation.get("parameters", []):
            if param["in"] == "header":
                headers.append(
                    {
                        "key": param["name"],
                        "value": self._get_example_value(param.get("schema", {})),
                        "description": param.get("description", ""),
                        "disabled": not param.get("required", False),
                    }
                )

        # Add Content-Type for requests with body
        request_body = operation.get("requestBody", {})
        if request_body:
            content = request_body.get("content", {})
            if "application/json" in content:
                headers.append(
                    {
                        "key": "Content-Type",
                        "value": "application/json",
                        "type": "text",
                    }
                )

        return headers

    def _build_body(self, operation: dict) -> dict | None:
        """Build request body from OpenAPI operation."""
        request_body = operation.get("requestBody", {})
        if not request_body:
            return None

        content = request_body.get("content", {})

        # Handle JSON body
        if "application/json" in content:
            json_content = content["application/json"]
            schema = json_content.get("schema", {})
            example = json_content.get("example") or self._generate_example(schema)

            return {
                "mode": "raw",
                "raw": json.dumps(example, indent=2),
                "options": {"raw": {"language": "json"}},
            }

        # Handle form data
        if "application/x-www-form-urlencoded" in content:
            form_content = content["application/x-www-form-urlencoded"]
            schema = form_content.get("schema", {})
            properties = schema.get("properties", {})

            form_data = []
            for prop_name, prop_schema in properties.items():
                form_data.append(
                    {
                        "key": prop_name,
                        "value": self._get_example_value(prop_schema),
                        "description": prop_schema.get("description", ""),
                        "type": "text",
                    }
                )

            return {"mode": "urlencoded", "urlencoded": form_data}

        # Handle multipart form data
        if "multipart/form-data" in content:
            multipart_content = content["multipart/form-data"]
            schema = multipart_content.get("schema", {})
            properties = schema.get("properties", {})

            form_data = []
            for prop_name, prop_schema in properties.items():
                item = {
                    "key": prop_name,
                    "description": prop_schema.get("description", ""),
                }

                if prop_schema.get("format") == "binary":
                    item["type"] = "file"
                    item["src"] = ""
                else:
                    item["type"] = "text"
                    item["value"] = self._get_example_value(prop_schema)

                form_data.append(item)

            return {"mode": "formdata", "formdata": form_data}

        return None

    def _build_example_responses(self, operation: dict) -> list[dict]:
        """Build example responses from OpenAPI operation."""
        examples = []

        for status_code, response in operation.get("responses", {}).items():
            response_name = f"Response {status_code}"
            description = response.get("description", "")

            content = response.get("content", {})
            body = ""

            if "application/json" in content:
                json_content = content["application/json"]
                example = json_content.get("example") or self._generate_example(
                    json_content.get("schema", {})
                )
                body = json.dumps(example, indent=2)

            examples.append(
                {
                    "name": response_name,
                    "originalRequest": {},
                    "status": description,
                    "code": int(status_code) if status_code.isdigit() else 200,
                    "body": body,
                }
            )

        return examples

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
        """Export and save the Postman collection."""
        collection = self.export()

        with open(output_path, "w") as f:
            json.dump(collection, f, indent=2)

        print(f"Exported Postman collection: {output_path}")


# =============================================================================
# Main
# =============================================================================


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Export Postman Collection from OpenAPI specification",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/openapi/export_postman.py openapi.json
    python scripts/openapi/export_postman.py openapi.json -o my_collection.json
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
        help="Output file path (default: <api_name>_postman_collection.json)",
    )

    args = parser.parse_args()

    # Validate input file
    if not args.spec_path.exists():
        print(f"Error: OpenAPI spec file not found: {args.spec_path}")
        sys.exit(1)

    # Create exporter
    exporter = PostmanExporter(args.spec_path)

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        safe_name = re.sub(r"[^a-zA-Z0-9]+", "_", exporter.api_title.lower())
        output_path = args.spec_path.parent / f"{safe_name}_postman_collection.json"

    print("=" * 60)
    print("Postman Collection Exporter")
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
    print(f"\nImport in Postman: File -> Import -> Select {output_path}")


if __name__ == "__main__":
    main()
