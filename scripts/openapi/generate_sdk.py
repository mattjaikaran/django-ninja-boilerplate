#!/usr/bin/env python
"""SDK Generator for TypeScript and Python clients.

This script generates SDK clients from an OpenAPI specification file.
It uses openapi-generator-cli for code generation.

Usage:
    python scripts/openapi/generate_sdk.py openapi.json --language typescript
    python scripts/openapi/generate_sdk.py openapi.json --language python
    python scripts/openapi/generate_sdk.py openapi.json --language all
"""

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# =============================================================================
# SDK Templates (for cases when openapi-generator is not available)
# =============================================================================

TYPESCRIPT_CLIENT_TEMPLATE = """/**
 * {api_title} - TypeScript SDK Client
 *
 * Auto-generated from OpenAPI specification
 * Generated at: {generated_at}
 * API Version: {api_version}
 *
 * This is a basic SDK client. For production use, consider using
 * openapi-generator-cli for a more complete implementation.
 */

export interface ApiConfig {{
  baseUrl: string;
  headers?: Record<string, string>;
  token?: string;
}}

export interface ApiResponse<T> {{
  data: T;
  status: number;
  ok: boolean;
}}

export class ApiError extends Error {{
  constructor(
    public status: number,
    public statusText: string,
    public data: unknown
  ) {{
    super(`API Error: ${{status}} ${{statusText}}`);
    this.name = 'ApiError';
  }}
}}

export class {class_name}Client {{
  private baseUrl: string;
  private headers: Record<string, string>;

  constructor(config: ApiConfig) {{
    this.baseUrl = config.baseUrl.replace(/\\/$/, '');
    this.headers = {{
      'Content-Type': 'application/json',
      ...config.headers,
    }};

    if (config.token) {{
      this.headers['Authorization'] = `Bearer ${{config.token}}`;
    }}
  }}

  /**
   * Set the authentication token
   */
  setToken(token: string): void {{
    this.headers['Authorization'] = `Bearer ${{token}}`;
  }}

  /**
   * Remove the authentication token
   */
  clearToken(): void {{
    delete this.headers['Authorization'];
  }}

  /**
   * Make an HTTP request
   */
  private async request<T>(
    method: string,
    path: string,
    body?: unknown,
    queryParams?: Record<string, string | number | boolean | undefined>
  ): Promise<ApiResponse<T>> {{
    let url = `${{this.baseUrl}}${{path}}`;

    // Add query parameters
    if (queryParams) {{
      const params = new URLSearchParams();
      Object.entries(queryParams).forEach(([key, value]) => {{
        if (value !== undefined) {{
          params.append(key, String(value));
        }}
      }});
      const queryString = params.toString();
      if (queryString) {{
        url += `?${{queryString}}`;
      }}
    }}

    const options: RequestInit = {{
      method,
      headers: this.headers,
    }};

    if (body && method !== 'GET') {{
      options.body = JSON.stringify(body);
    }}

    const response = await fetch(url, options);

    let data: T;
    try {{
      data = await response.json();
    }} catch {{
      data = null as T;
    }}

    if (!response.ok) {{
      throw new ApiError(response.status, response.statusText, data);
    }}

    return {{
      data,
      status: response.status,
      ok: response.ok,
    }};
  }}

  // ===========================================================================
  // Generated API Methods
  // ===========================================================================

{methods}
}}

// ===========================================================================
// Type Definitions
// ===========================================================================

{types}

// ===========================================================================
// Default Export
// ===========================================================================

export default {class_name}Client;
"""

TYPESCRIPT_METHOD_TEMPLATE = """  /**
   * {summary}
   * {description}
   *
   * @param {params_doc}
   * @returns Promise<ApiResponse<{return_type}>>
   */
  async {method_name}({params}): Promise<ApiResponse<{return_type}>> {{
    return this.request<{return_type}>('{http_method}', `{path}`{body_param}{query_param});
  }}
"""

PYTHON_CLIENT_TEMPLATE = '''"""
{api_title} - Python SDK Client

Auto-generated from OpenAPI specification
Generated at: {generated_at}
API Version: {api_version}

This is a basic SDK client. For production use, consider using
openapi-generator-cli for a more complete implementation.
"""

from dataclasses import dataclass
from typing import Any, TypeVar, Generic
from urllib.parse import urljoin, urlencode

import httpx


T = TypeVar("T")


@dataclass
class ApiConfig:
    """API client configuration."""

    base_url: str
    token: str | None = None
    headers: dict[str, str] | None = None
    timeout: float = 30.0


@dataclass
class ApiResponse(Generic[T]):
    """API response wrapper."""

    data: T
    status: int
    ok: bool


class ApiError(Exception):
    """API error exception."""

    def __init__(self, status: int, status_text: str, data: Any) -> None:
        super().__init__(f"API Error: {{status}} {{status_text}}")
        self.status = status
        self.status_text = status_text
        self.data = data


class {class_name}Client:
    """
    {api_title} API Client

    Usage:
        client = {class_name}Client(ApiConfig(base_url="http://localhost:8000/api"))
        client.set_token("your-jwt-token")

        # Make API calls
        response = client.health_check()
        print(response.data)
    """

    def __init__(self, config: ApiConfig) -> None:
        """Initialize the API client."""
        self.base_url = config.base_url.rstrip("/")
        self.timeout = config.timeout

        self.headers = {{
            "Content-Type": "application/json",
            **(config.headers or {{}}),
        }}

        if config.token:
            self.headers["Authorization"] = f"Bearer {{config.token}}"

        self._client = httpx.Client(
            base_url=self.base_url,
            headers=self.headers,
            timeout=self.timeout,
        )

    def __enter__(self) -> "{class_name}Client":
        """Context manager entry."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit."""
        self.close()

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def set_token(self, token: str) -> None:
        """Set the authentication token."""
        self.headers["Authorization"] = f"Bearer {{token}}"
        self._client.headers["Authorization"] = f"Bearer {{token}}"

    def clear_token(self) -> None:
        """Remove the authentication token."""
        self.headers.pop("Authorization", None)
        self._client.headers.pop("Authorization", None)

    def _request(
        self,
        method: str,
        path: str,
        body: Any | None = None,
        query_params: dict[str, Any] | None = None,
    ) -> ApiResponse[Any]:
        """Make an HTTP request."""
        url = path

        # Add query parameters
        if query_params:
            filtered_params = {{k: v for k, v in query_params.items() if v is not None}}
            if filtered_params:
                url = f"{{url}}?{{urlencode(filtered_params)}}"

        request_kwargs: dict[str, Any] = {{"method": method, "url": url}}

        if body is not None and method != "GET":
            request_kwargs["json"] = body

        response = self._client.request(**request_kwargs)

        try:
            data = response.json()
        except Exception:
            data = None

        if not response.is_success:
            raise ApiError(response.status_code, response.reason_phrase, data)

        return ApiResponse(
            data=data,
            status=response.status_code,
            ok=response.is_success,
        )

    # =========================================================================
    # Generated API Methods
    # =========================================================================

{methods}


# =============================================================================
# Async Client
# =============================================================================


class Async{class_name}Client:
    """
    Async {api_title} API Client

    Usage:
        async with Async{class_name}Client(ApiConfig(base_url="http://localhost:8000/api")) as client:
            client.set_token("your-jwt-token")
            response = await client.health_check()
            print(response.data)
    """

    def __init__(self, config: ApiConfig) -> None:
        """Initialize the async API client."""
        self.base_url = config.base_url.rstrip("/")
        self.timeout = config.timeout

        self.headers = {{
            "Content-Type": "application/json",
            **(config.headers or {{}}),
        }}

        if config.token:
            self.headers["Authorization"] = f"Bearer {{config.token}}"

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            timeout=self.timeout,
        )

    async def __aenter__(self) -> "Async{class_name}Client":
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        await self.close()

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    def set_token(self, token: str) -> None:
        """Set the authentication token."""
        self.headers["Authorization"] = f"Bearer {{token}}"
        self._client.headers["Authorization"] = f"Bearer {{token}}"

    def clear_token(self) -> None:
        """Remove the authentication token."""
        self.headers.pop("Authorization", None)
        self._client.headers.pop("Authorization", None)

    async def _request(
        self,
        method: str,
        path: str,
        body: Any | None = None,
        query_params: dict[str, Any] | None = None,
    ) -> ApiResponse[Any]:
        """Make an async HTTP request."""
        url = path

        # Add query parameters
        if query_params:
            filtered_params = {{k: v for k, v in query_params.items() if v is not None}}
            if filtered_params:
                url = f"{{url}}?{{urlencode(filtered_params)}}"

        request_kwargs: dict[str, Any] = {{"method": method, "url": url}}

        if body is not None and method != "GET":
            request_kwargs["json"] = body

        response = await self._client.request(**request_kwargs)

        try:
            data = response.json()
        except Exception:
            data = None

        if not response.is_success:
            raise ApiError(response.status_code, response.reason_phrase, data)

        return ApiResponse(
            data=data,
            status=response.status_code,
            ok=response.is_success,
        )

    # =========================================================================
    # Generated Async API Methods
    # =========================================================================

{async_methods}
'''

PYTHON_METHOD_TEMPLATE = '''    def {method_name}(
        self,
{params}
    ) -> ApiResponse[Any]:
        """
        {summary}

        {description}

        Args:
{args_doc}

        Returns:
            ApiResponse containing the response data
        """
        return self._request(
            "{http_method}",
            {path},
{body_param}{query_param}
        )
'''

PYTHON_ASYNC_METHOD_TEMPLATE = '''    async def {method_name}(
        self,
{params}
    ) -> ApiResponse[Any]:
        """
        {summary}

        {description}

        Args:
{args_doc}

        Returns:
            ApiResponse containing the response data
        """
        return await self._request(
            "{http_method}",
            {path},
{body_param}{query_param}
        )
'''


# =============================================================================
# Helper Functions
# =============================================================================


def to_camel_case(snake_str: str) -> str:
    """Convert snake_case to camelCase."""
    components = snake_str.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


def to_pascal_case(text: str) -> str:
    """Convert text to PascalCase."""
    import re

    words = re.split(r"[^a-zA-Z0-9]+", text)
    return "".join(word.capitalize() for word in words if word)


def to_snake_case(text: str) -> str:
    """Convert text to snake_case."""
    import re

    # Handle camelCase
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", text)
    # Handle acronyms
    s2 = re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1)
    # Replace non-alphanumeric with underscore
    s3 = re.sub(r"[^a-zA-Z0-9]+", "_", s2)
    return s3.lower().strip("_")


def openapi_type_to_typescript(schema: dict) -> str:
    """Convert OpenAPI type to TypeScript type."""
    if not schema:
        return "unknown"

    if "$ref" in schema:
        ref = schema["$ref"]
        return ref.split("/")[-1]

    schema_type = schema.get("type", "object")

    type_mapping = {
        "string": "string",
        "integer": "number",
        "number": "number",
        "boolean": "boolean",
        "null": "null",
    }

    if schema_type == "array":
        items_type = openapi_type_to_typescript(schema.get("items", {}))
        return f"{items_type}[]"

    if schema_type == "object":
        if "properties" in schema:
            return "Record<string, unknown>"
        if "additionalProperties" in schema:
            value_type = openapi_type_to_typescript(schema["additionalProperties"])
            return f"Record<string, {value_type}>"
        return "Record<string, unknown>"

    return type_mapping.get(schema_type, "unknown")


def openapi_type_to_python(schema: dict) -> str:
    """Convert OpenAPI type to Python type hint."""
    if not schema:
        return "Any"

    if "$ref" in schema:
        ref = schema["$ref"]
        return ref.split("/")[-1]

    schema_type = schema.get("type", "object")

    type_mapping = {
        "string": "str",
        "integer": "int",
        "number": "float",
        "boolean": "bool",
        "null": "None",
    }

    if schema_type == "array":
        items_type = openapi_type_to_python(schema.get("items", {}))
        return f"list[{items_type}]"

    if schema_type == "object":
        return "dict[str, Any]"

    return type_mapping.get(schema_type, "Any")


# =============================================================================
# SDK Generator
# =============================================================================


class SDKGenerator:
    """Generate SDK clients from OpenAPI specification."""

    def __init__(self, spec_path: Path, output_dir: Path) -> None:
        """Initialize the SDK generator."""
        self.spec_path = spec_path
        self.output_dir = output_dir

        with open(spec_path) as f:
            self.spec = json.load(f)

        self.api_title = self.spec.get("info", {}).get("title", "API")
        self.api_version = self.spec.get("info", {}).get("version", "1.0.0")
        self.class_name = to_pascal_case(self.api_title.replace("API", "").strip())

        if not self.class_name:
            self.class_name = "Api"

    def generate_typescript(self) -> Path:
        """Generate TypeScript SDK client."""
        output_path = self.output_dir / "typescript"
        output_path.mkdir(parents=True, exist_ok=True)

        methods = []
        types = []

        # Generate methods from paths
        for path, path_item in self.spec.get("paths", {}).items():
            for method, operation in path_item.items():
                if method not in ("get", "post", "put", "patch", "delete"):
                    continue

                method_code = self._generate_typescript_method(path, method, operation)
                methods.append(method_code)

        # Generate types from components/schemas
        for name, schema in self.spec.get("components", {}).get("schemas", {}).items():
            type_code = self._generate_typescript_type(name, schema)
            types.append(type_code)

        # Write the client file
        client_content = TYPESCRIPT_CLIENT_TEMPLATE.format(
            api_title=self.api_title,
            api_version=self.api_version,
            class_name=self.class_name,
            generated_at=datetime.now().isoformat(),
            methods="\n".join(methods),
            types="\n".join(types),
        )

        client_file = output_path / "client.ts"
        with open(client_file, "w") as f:
            f.write(client_content)

        # Write package.json
        package_json = {
            "name": f"@api/{to_snake_case(self.api_title).replace('_', '-')}-client",
            "version": self.api_version,
            "description": f"TypeScript SDK client for {self.api_title}",
            "main": "dist/client.js",
            "types": "dist/client.d.ts",
            "scripts": {
                "build": "tsc",
                "prepublishOnly": "npm run build",
            },
            "devDependencies": {"typescript": "^5.0.0"},
            "files": ["dist"],
        }

        with open(output_path / "package.json", "w") as f:
            json.dump(package_json, f, indent=2)

        # Write tsconfig.json
        tsconfig = {
            "compilerOptions": {
                "target": "ES2020",
                "module": "ESNext",
                "moduleResolution": "node",
                "declaration": True,
                "outDir": "./dist",
                "strict": True,
                "esModuleInterop": True,
            },
            "include": ["*.ts"],
        }

        with open(output_path / "tsconfig.json", "w") as f:
            json.dump(tsconfig, f, indent=2)

        print(f"Generated TypeScript SDK: {output_path}")
        return output_path

    def _generate_typescript_method(
        self, path: str, method: str, operation: dict
    ) -> str:
        """Generate a TypeScript method for an operation."""
        operation_id = operation.get("operationId", f"{method}_{path}")
        method_name = to_camel_case(to_snake_case(operation_id))
        summary = operation.get("summary", "")
        description = operation.get("description", "")

        # Parse parameters
        params = []
        params_doc = []
        query_params = []
        path_params = []

        for param in operation.get("parameters", []):
            param_name = param["name"]
            param_type = openapi_type_to_typescript(param.get("schema", {}))
            required = param.get("required", False)

            if param["in"] == "path":
                path_params.append(param_name)
                params.append(f"{param_name}: {param_type}")
            elif param["in"] == "query":
                if required:
                    params.append(f"{param_name}: {param_type}")
                else:
                    params.append(f"{param_name}?: {param_type}")
                query_params.append(param_name)

            params_doc.append(f"{param_name} - {param.get('description', '')}")

        # Check for request body
        body_param = ""
        request_body = operation.get("requestBody", {})
        if request_body:
            content = request_body.get("content", {})
            json_content = content.get("application/json", {})
            body_schema = json_content.get("schema", {})
            body_type = openapi_type_to_typescript(body_schema)
            params.insert(0, f"body: {body_type}")
            body_param = ", body"
            params_doc.insert(0, "body - Request body")

        # Get return type
        responses = operation.get("responses", {})
        success_response = responses.get("200", responses.get("201", {}))
        response_content = success_response.get("content", {})
        response_schema = response_content.get("application/json", {}).get("schema", {})
        return_type = openapi_type_to_typescript(response_schema)

        # Build path with interpolation
        ts_path = path
        for param in path_params:
            ts_path = ts_path.replace(f"{{{param}}}", f"${{{param}}}")

        # Build query params
        query_param = ""
        if query_params:
            query_obj = ", ".join(query_params)
            query_param = f", {{ {query_obj} }}"

        return TYPESCRIPT_METHOD_TEMPLATE.format(
            method_name=method_name,
            summary=summary,
            description=description,
            params=", ".join(params) if params else "",
            params_doc=", ".join(params_doc) if params_doc else "None",
            return_type=return_type or "unknown",
            http_method=method.upper(),
            path=ts_path,
            body_param=body_param,
            query_param=query_param,
        )

    def _generate_typescript_type(self, name: str, schema: dict) -> str:
        """Generate a TypeScript interface from a schema."""
        if schema.get("type") == "object":
            properties = schema.get("properties", {})
            required = schema.get("required", [])

            fields = []
            for prop_name, prop_schema in properties.items():
                prop_type = openapi_type_to_typescript(prop_schema)
                optional = "" if prop_name in required else "?"
                description = prop_schema.get("description", "")
                comment = f"  /** {description} */\n" if description else ""
                fields.append(f"{comment}  {prop_name}{optional}: {prop_type};")

            return f"export interface {name} {{\n" + "\n".join(fields) + "\n}\n"

        return f"export type {name} = {openapi_type_to_typescript(schema)};\n"

    def generate_python(self) -> Path:
        """Generate Python SDK client."""
        output_path = self.output_dir / "python"
        output_path.mkdir(parents=True, exist_ok=True)

        methods = []
        async_methods = []

        # Generate methods from paths
        for path, path_item in self.spec.get("paths", {}).items():
            for method, operation in path_item.items():
                if method not in ("get", "post", "put", "patch", "delete"):
                    continue

                sync_method = self._generate_python_method(path, method, operation)
                async_method = self._generate_python_async_method(
                    path, method, operation
                )
                methods.append(sync_method)
                async_methods.append(async_method)

        # Write the client file
        client_content = PYTHON_CLIENT_TEMPLATE.format(
            api_title=self.api_title,
            api_version=self.api_version,
            class_name=self.class_name,
            generated_at=datetime.now().isoformat(),
            methods="\n".join(methods),
            async_methods="\n".join(async_methods),
        )

        client_file = output_path / "client.py"
        with open(client_file, "w") as f:
            f.write(client_content)

        # Write __init__.py
        init_content = f'''"""
{self.api_title} Python SDK

Auto-generated from OpenAPI specification.
"""

from .client import (
    ApiConfig,
    ApiError,
    ApiResponse,
    Async{self.class_name}Client,
    {self.class_name}Client,
)

__all__ = [
    "ApiConfig",
    "ApiError",
    "ApiResponse",
    "{self.class_name}Client",
    "Async{self.class_name}Client",
]
'''

        with open(output_path / "__init__.py", "w") as f:
            f.write(init_content)

        # Write pyproject.toml
        package_name = to_snake_case(self.api_title).replace("_", "-") + "-client"
        pyproject = f"""[project]
name = "{package_name}"
version = "{self.api_version}"
description = "Python SDK client for {self.api_title}"
requires-python = ">=3.10"
dependencies = [
    "httpx>=0.25.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
"""

        with open(output_path / "pyproject.toml", "w") as f:
            f.write(pyproject)

        print(f"Generated Python SDK: {output_path}")
        return output_path

    def _generate_python_method(self, path: str, method: str, operation: dict) -> str:
        """Generate a Python method for an operation."""
        operation_id = operation.get("operationId", f"{method}_{path}")
        method_name = to_snake_case(operation_id)
        summary = operation.get("summary", "No description")
        description = operation.get("description", "")

        # Parse parameters
        params = []
        args_doc = []
        query_params = []
        path_params = []

        for param in operation.get("parameters", []):
            param_name = to_snake_case(param["name"])
            param_type = openapi_type_to_python(param.get("schema", {}))
            required = param.get("required", False)
            param_desc = param.get("description", "")

            if param["in"] == "path":
                path_params.append((param["name"], param_name))
                params.append(f"        {param_name}: {param_type},")
                args_doc.append(f"            {param_name}: {param_desc}")
            elif param["in"] == "query":
                if required:
                    params.append(f"        {param_name}: {param_type},")
                else:
                    params.append(f"        {param_name}: {param_type} | None = None,")
                query_params.append(param_name)
                args_doc.append(f"            {param_name}: {param_desc}")

        # Check for request body
        body_param = ""
        request_body = operation.get("requestBody", {})
        if request_body:
            params.insert(0, "        body: dict[str, Any],")
            body_param = "            body=body,\n"
            args_doc.insert(0, "            body: Request body")

        # Build path with f-string
        py_path = f'f"{path}"'
        for orig_name, snake_name in path_params:
            py_path = py_path.replace(f"{{{orig_name}}}", f"{{{snake_name}}}")

        # Build query params
        query_param = ""
        if query_params:
            query_dict = ", ".join(f'"{p}": {p}' for p in query_params)
            query_param = f"            query_params={{{query_dict}}},\n"

        return PYTHON_METHOD_TEMPLATE.format(
            method_name=method_name,
            summary=summary,
            description=description,
            params="\n".join(params) if params else "        *,",
            args_doc="\n".join(args_doc) if args_doc else "            None",
            http_method=method.upper(),
            path=py_path,
            body_param=body_param,
            query_param=query_param,
        )

    def _generate_python_async_method(
        self, path: str, method: str, operation: dict
    ) -> str:
        """Generate an async Python method for an operation."""
        operation_id = operation.get("operationId", f"{method}_{path}")
        method_name = to_snake_case(operation_id)
        summary = operation.get("summary", "No description")
        description = operation.get("description", "")

        # Parse parameters
        params = []
        args_doc = []
        query_params = []
        path_params = []

        for param in operation.get("parameters", []):
            param_name = to_snake_case(param["name"])
            param_type = openapi_type_to_python(param.get("schema", {}))
            required = param.get("required", False)
            param_desc = param.get("description", "")

            if param["in"] == "path":
                path_params.append((param["name"], param_name))
                params.append(f"        {param_name}: {param_type},")
                args_doc.append(f"            {param_name}: {param_desc}")
            elif param["in"] == "query":
                if required:
                    params.append(f"        {param_name}: {param_type},")
                else:
                    params.append(f"        {param_name}: {param_type} | None = None,")
                query_params.append(param_name)
                args_doc.append(f"            {param_name}: {param_desc}")

        # Check for request body
        body_param = ""
        request_body = operation.get("requestBody", {})
        if request_body:
            params.insert(0, "        body: dict[str, Any],")
            body_param = "            body=body,\n"
            args_doc.insert(0, "            body: Request body")

        # Build path with f-string
        py_path = f'f"{path}"'
        for orig_name, snake_name in path_params:
            py_path = py_path.replace(f"{{{orig_name}}}", f"{{{snake_name}}}")

        # Build query params
        query_param = ""
        if query_params:
            query_dict = ", ".join(f'"{p}": {p}' for p in query_params)
            query_param = f"            query_params={{{query_dict}}},\n"

        return PYTHON_ASYNC_METHOD_TEMPLATE.format(
            method_name=method_name,
            summary=summary,
            description=description,
            params="\n".join(params) if params else "        *,",
            args_doc="\n".join(args_doc) if args_doc else "            None",
            http_method=method.upper(),
            path=py_path,
            body_param=body_param,
            query_param=query_param,
        )

    def generate_with_openapi_generator(self, language: str) -> Path | None:
        """Generate SDK using openapi-generator-cli if available."""
        # Check if openapi-generator-cli is available
        if not shutil.which("openapi-generator-cli") and not shutil.which(
            "openapi-generator"
        ):
            return None

        generator_cmd = (
            "openapi-generator-cli"
            if shutil.which("openapi-generator-cli")
            else "openapi-generator"
        )

        generator_map = {
            "typescript": "typescript-fetch",
            "python": "python",
        }

        if language not in generator_map:
            print(f"Unsupported language for openapi-generator: {language}")
            return None

        output_path = self.output_dir / f"{language}-generated"
        output_path.mkdir(parents=True, exist_ok=True)

        cmd = [
            generator_cmd,
            "generate",
            "-i",
            str(self.spec_path),
            "-g",
            generator_map[language],
            "-o",
            str(output_path),
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True)
            print(f"Generated {language} SDK with openapi-generator: {output_path}")
            return output_path
        except subprocess.CalledProcessError as e:
            print(f"openapi-generator failed: {e.stderr.decode()}")
            return None


# =============================================================================
# Main
# =============================================================================


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate SDK clients from OpenAPI specification",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/openapi/generate_sdk.py openapi.json --language typescript
    python scripts/openapi/generate_sdk.py openapi.json --language python
    python scripts/openapi/generate_sdk.py openapi.json --language all
    python scripts/openapi/generate_sdk.py openapi.json -o ./sdk --language all
        """,
    )

    parser.add_argument(
        "spec_path",
        type=Path,
        help="Path to OpenAPI specification file (JSON or YAML)",
    )

    parser.add_argument(
        "--language",
        "-l",
        choices=["typescript", "python", "all"],
        default="all",
        help="Target language for SDK generation (default: all)",
    )

    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("docs/openapi/sdk"),
        help="Output directory for generated SDKs (default: docs/openapi/sdk)",
    )

    parser.add_argument(
        "--use-generator",
        action="store_true",
        help="Use openapi-generator-cli if available (produces more complete SDKs)",
    )

    args = parser.parse_args()

    # Validate input file
    if not args.spec_path.exists():
        print(f"Error: OpenAPI spec file not found: {args.spec_path}")
        sys.exit(1)

    # Create generator
    generator = SDKGenerator(args.spec_path, args.output)

    print("=" * 60)
    print("SDK Generator")
    print("=" * 60)
    print(f"Input:    {args.spec_path}")
    print(f"Output:   {args.output}")
    print(f"API:      {generator.api_title} v{generator.api_version}")
    print(f"Language: {args.language}")
    print("=" * 60)

    generated = []

    if args.language in ("typescript", "all"):
        if args.use_generator:
            path = generator.generate_with_openapi_generator("typescript")
            if path:
                generated.append(path)
            else:
                path = generator.generate_typescript()
                generated.append(path)
        else:
            path = generator.generate_typescript()
            generated.append(path)

    if args.language in ("python", "all"):
        if args.use_generator:
            path = generator.generate_with_openapi_generator("python")
            if path:
                generated.append(path)
            else:
                path = generator.generate_python()
                generated.append(path)
        else:
            path = generator.generate_python()
            generated.append(path)

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Generated {len(generated)} SDK(s):")
    for path in generated:
        print(f"  - {path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
