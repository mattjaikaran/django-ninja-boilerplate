"""Engine generator: a bounded context that groups several module apps."""

from __future__ import annotations

import dataclasses
import keyword

from core.management.commands.startapp_extended import add_wheel_package

from .base_generator import BaseGenerator, GeneratorError
from .codegen import (
    PACKAGE_INIT,
    ResourceNames,
    from_import,
    import_block,
    method_def,
    package_init,
)
from .templates.engine_templates import (
    ADMIN_TEMPLATE,
    APPS_TEMPLATE,
    BOUNDARY_TESTS_TEMPLATE,
    CONTROLLER_TEMPLATE,
    DTO_TEMPLATE,
    ENGINE_README_TEMPLATE,
    ENGINE_SERVICE_TEMPLATE,
    MODEL_TEMPLATE,
    REPOSITORY_TEMPLATE,
    SCHEMA_TEMPLATE,
    SERVICE_TEMPLATE,
)

ENGINES_DIR = "engines"
# Layer packages inside a module. An engine or module may not take these names.
RESERVED_NAMES = frozenset(
    {
        "admin",
        "controllers",
        "dtos",
        "migrations",
        "models",
        "repositories",
        "schemas",
        "services",
        "tasks",
        "tests",
    }
)


class EngineGenerator(BaseGenerator):
    """Generator for an engine: a bounded context of owner-scoped modules.

    The engine lives at ``engines/<engine>``. Each module is a Django app at
    ``engines/<engine>/<module>`` with one CRUD resource: model, repository,
    DTOs, service, schemas, controller, admin and boundary tests. The engine
    service composes the module services.
    """

    def __init__(
        self,
        app_name: str,
        modules: list[str] | None = None,
        minimal: bool = False,
    ):
        """Initialize the generator.

        Args:
            app_name: Engine name, such as ``booking``
            modules: Module names. Defaults to one module named after the engine
            minimal: Whether to generate minimal version
        """
        super().__init__(app_name, minimal=minimal)
        self.engine = app_name
        self.modules = modules or [app_name]
        self.app_path = self.project_root / ENGINES_DIR / self.engine
        self._validate_names()

    def _validate_names(self) -> None:
        """Reject engine and module names that are not plain, free identifiers."""
        for name in (self.engine, *self.modules):
            if (
                not name.isidentifier()
                or name != name.lower()
                or keyword.iskeyword(name)
                or name in RESERVED_NAMES
            ):
                msg = f"'{name}' is not a valid engine or module name"
                raise GeneratorError(msg)
        if len(set(self.modules)) != len(self.modules):
            msg = f"Module names must be unique: {', '.join(self.modules)}"
            raise GeneratorError(msg)

    @staticmethod
    def _title(name: str) -> str:
        """Return a display title, such as ``Tour Dates`` for ``tour_dates``."""
        return " ".join(part.capitalize() for part in name.split("_"))

    @staticmethod
    def _pascal(name: str) -> str:
        """Return a class-name stem, such as ``TourDates`` for ``tour_dates``."""
        return "".join(part.capitalize() for part in name.split("_"))

    def _context(self, module: str) -> dict[str, str]:
        """Return the template arguments for one module of the engine."""
        dotted = f"{ENGINES_DIR}.{self.engine}.{module}"
        names = ResourceNames.from_app_name(module)
        engine_title = self._title(self.engine)
        return {
            **dataclasses.replace(names, app_name=dotted).context(),
            "tag": f"{engine_title} {names.tag}",
            "engine": self.engine,
            "engine_title": engine_title,
            "engine_class": self._pascal(self.engine),
            "module_title": self._title(module),
            "module_class": self._pascal(module),
            "app_label": f"{self.engine}_{module}",
            "controller_class": (
                f"{self._pascal(self.engine)}{names.model_name}Controller"
            ),
        }

    def generate(self) -> None:
        """Generate the engine, its module apps and the engine service."""
        if self.app_path.exists():
            msg = f"Engine '{self.engine}' already exists at {self.app_path}"
            raise GeneratorError(msg)

        self.logger.info(
            "Generating engine %s with modules %s",
            self.engine,
            ", ".join(self.modules),
        )
        self.create_file(
            self.project_root / ENGINES_DIR / "__init__.py",
            PACKAGE_INIT,
            overwrite=False,
        )
        self.create_file(self.app_path / "__init__.py", PACKAGE_INIT)
        self.create_file(self.app_path / "README.md", self._readme())
        # An installed app missing from the wheel breaks django.setup() there.
        if add_wheel_package(self.project_root / "pyproject.toml", ENGINES_DIR):
            self.logger.info("Added %s to the Hatch wheel packages", ENGINES_DIR)
        for module in self.modules:
            self._generate_module(module)
        self._generate_engine_service()
        self.run_ruff("check", "--fix", "--select", "I", self.app_path)
        self.run_ruff("format", self.app_path)

        self.logger.info("Successfully generated engine %s", self.engine)

    def _readme(self) -> str:
        """Return the engine README listing its modules."""
        module_list = "\n".join(
            f"- `{ENGINES_DIR}.{self.engine}.{module}`" for module in self.modules
        )
        return ENGINE_README_TEMPLATE.format(
            engine=self.engine,
            engine_title=self._title(self.engine),
            module_list=module_list,
        )

    def _generate_module(self, module: str) -> None:
        """Write one module app, then register it and create its migration."""
        ctx = self._context(module)
        module_dir = self.app_path / module
        for relative_path, content in self._module_files(ctx).items():
            self.create_file(module_dir / relative_path, content)
        self.run_ruff("check", "--fix", "--select", "I", module_dir)
        self.run_ruff("format", module_dir)
        self.update_settings(ctx["app_name"], {})
        self.update_urls(ctx["app_name"], ctx["controller_class"])
        self.create_migration(label=ctx["app_label"], app_dir=module_dir)

    def _module_files(self, ctx: dict[str, str]) -> dict[str, str]:
        """Return the file contents of one module, keyed by module-relative path."""
        dotted = ctx["app_name"]
        model = ctx["model_name"]
        snake = ctx["model_snake"]
        controller = ctx["controller_class"]
        dto = f"{model}DTO"
        repository = f"{model}Repository"
        service = f"{model}Service"
        create_schema = f"Create{model}Schema"
        update_schema = f"Update{model}Schema"
        model_import = from_import(f"{dotted}.models", model)
        dto_import = from_import(f"{dotted}.dtos", dto)
        schema_import = from_import(
            f"{dotted}.schemas", f"{model}Schema", create_schema, update_schema
        )
        service_import = from_import(f"{dotted}.services", service)
        repository_import = from_import(f"{dotted}.repositories", repository)

        return {
            "__init__.py": PACKAGE_INIT,
            "apps.py": APPS_TEMPLATE.format(**ctx),
            "models/__init__.py": package_init((f"{dotted}.models.{snake}", [model])),
            f"models/{snake}.py": MODEL_TEMPLATE.format(**ctx),
            "dtos/__init__.py": package_init((f"{dotted}.dtos.{snake}_dto", [dto])),
            f"dtos/{snake}_dto.py": DTO_TEMPLATE.format(**ctx),
            "repositories/__init__.py": package_init(
                (f"{dotted}.repositories.{snake}_repository", [repository])
            ),
            f"repositories/{snake}_repository.py": REPOSITORY_TEMPLATE.format(
                first_party_imports=import_block(dto_import, model_import), **ctx
            ),
            "services/__init__.py": package_init(
                (f"{dotted}.services.{snake}_service", [service])
            ),
            f"services/{snake}_service.py": SERVICE_TEMPLATE.format(
                first_party_imports=import_block(
                    from_import("api.exceptions", "NotFoundError"),
                    dto_import,
                    repository_import,
                    from_import(f"{dotted}.schemas", create_schema, update_schema),
                ),
                create_def=method_def(
                    "create",
                    f"self, owner_id: UUID, payload: {create_schema}",
                    dto,
                ),
                update_def=method_def(
                    "update",
                    f"self, item_id: UUID, owner_id: UUID, payload: {update_schema}",
                    dto,
                ),
                **ctx,
            ),
            "schemas/__init__.py": package_init(
                (
                    f"{dotted}.schemas.{snake}_schema",
                    [f"{model}Schema", create_schema, update_schema],
                )
            ),
            f"schemas/{snake}_schema.py": SCHEMA_TEMPLATE.format(**ctx),
            "controllers/__init__.py": package_init(
                (f"{dotted}.controllers.{snake}_controller", [controller])
            ),
            f"controllers/{snake}_controller.py": CONTROLLER_TEMPLATE.format(
                first_party_imports=import_block(
                    "from api.decorators import log_api_call",
                    schema_import,
                    service_import,
                ),
                create_def=method_def(
                    f"create_{snake}", f"self, request, payload: {create_schema}"
                ),
                update_def=method_def(
                    f"update_{snake}",
                    f"self, request, item_id: UUID, payload: {update_schema}",
                ),
                **ctx,
            ),
            "admin/__init__.py": package_init(
                (f"{dotted}.admin.{snake}_admin", [f"{model}Admin"])
            ),
            f"admin/{snake}_admin.py": ADMIN_TEMPLATE.format(
                first_party_imports=model_import, **ctx
            ),
            "migrations/__init__.py": PACKAGE_INIT,
            "tests/__init__.py": PACKAGE_INIT,
            f"tests/test_{ctx['route']}_boundary.py": BOUNDARY_TESTS_TEMPLATE.format(
                first_party_imports=import_block(
                    "from core.tests.factories import UserFactory",
                    model_import,
                ),
                **ctx,
            ),
        }

    def _generate_engine_service(self) -> None:
        """Write the engine-level service that composes the module services."""
        dotted_engine = f"{ENGINES_DIR}.{self.engine}"
        engine_class = f"{self._pascal(self.engine)}EngineService"
        models = {
            module: ResourceNames.from_app_name(module).model_name
            for module in self.modules
        }
        imports = import_block(
            *(
                from_import(f"{dotted_engine}.{module}.services", f"{model}Service")
                for module, model in models.items()
            )
        )
        attributes = "\n".join(
            f"        self.{module} = {model}Service()"
            for module, model in models.items()
        )
        services_dir = self.app_path / "services"
        self.create_file(
            services_dir / f"{self.engine}_engine_service.py",
            ENGINE_SERVICE_TEMPLATE.format(
                engine=self.engine,
                engine_class=self._pascal(self.engine),
                first_party_imports=imports,
                attributes=attributes,
            ),
        )
        self.create_file(
            services_dir / "__init__.py",
            package_init(
                (
                    f"{dotted_engine}.services.{self.engine}_engine_service",
                    [engine_class],
                )
            ),
        )
