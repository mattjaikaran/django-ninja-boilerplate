"""Naming and import helpers shared by the app and feature generators."""

from __future__ import annotations

from dataclasses import dataclass

# Words that end in "s" but are already singular.
_SINGULAR_ENDINGS = ("ss", "us", "is")
# Plural endings that drop "es" to get the singular form.
_ES_PLURAL_ENDINGS = ("sses", "xes", "ches", "shes")
# Singular endings that take "es" in the plural.
_ES_SINGULAR_ENDINGS = ("s", "x", "z", "ch", "sh")


def singularize(word: str) -> str:
    """Return the singular form of a lowercase English noun.

    Covers the regular forms only: "ies" -> "y", "es" after ss/x/ch/sh, and
    a trailing "s". Words that end in "ss", "us" or "is" stay as they are.
    """
    if word.endswith("ies") and len(word) > 3:
        return word[:-3] + "y"
    if word.endswith(_ES_PLURAL_ENDINGS):
        return word[:-2]
    if word.endswith("s") and not word.endswith(_SINGULAR_ENDINGS):
        return word[:-1]
    return word


def pluralize(word: str) -> str:
    """Return the plural form of a singular lowercase English noun."""
    if word.endswith("y") and len(word) > 1 and word[-2] not in "aeiou":
        return word[:-1] + "ies"
    if word.endswith(_ES_SINGULAR_ENDINGS):
        return word + "es"
    return word + "s"


@dataclass(frozen=True)
class ResourceNames:
    """Names derived from an app name for one generated CRUD resource.

    ``gadgets`` and ``gadget`` both give model ``Gadget``, module ``gadget``
    and route ``gadgets``.
    """

    app_name: str
    model_name: str
    model_snake: str
    route: str
    tag: str

    @classmethod
    def from_app_name(cls, app_name: str) -> ResourceNames:
        """Derive the singular model and plural route names from an app name."""
        *head, last = app_name.lower().split("_")
        model_snake = "_".join([*head, singularize(last)])
        route = "_".join([*head, pluralize(singularize(last))])
        return cls(
            app_name=app_name,
            model_name="".join(part.capitalize() for part in model_snake.split("_")),
            model_snake=model_snake,
            route=route,
            tag=" ".join(part.capitalize() for part in route.split("_")),
        )

    def context(self) -> dict[str, str]:
        """Return the names as template format arguments."""
        return {
            "app_name": self.app_name,
            "model_name": self.model_name,
            "model_snake": self.model_snake,
            "route": self.route,
            "tag": self.tag,
        }


def method_def(name: str, params: str, returns: str = "") -> str:
    """Return a ``def`` line for a class method in ``ruff format`` layout.

    The signature stays on one line when it fits in 88 characters. Otherwise
    the parameters move to their own line.
    """
    tail = f") -> {returns}:" if returns else "):"
    line = f"    def {name}({params}{tail}"
    if len(line) <= 88:
        return line
    return f"    def {name}(\n        {params}\n    {tail}"


def from_import(module: str, *names: str) -> str:
    """Return ``from module import names`` with the names in isort order.

    The statement wraps one name per line, with a trailing comma, when it
    does not fit in 88 characters.
    """
    ordered = sorted(names, key=str.lower)
    line = f"from {module} import {', '.join(ordered)}"
    if len(line) <= 88:
        return line
    body = "".join(f"    {name},\n" for name in ordered)
    return f"from {module} import (\n{body})"


def import_block(*statements: str) -> str:
    """Join ``from x import y`` statements of one isort section in module order.

    Generated files import the app itself next to ``api``, ``core`` and
    ``tests``, so the order depends on the app name.
    """
    return "\n".join(sorted(statements, key=lambda line: line.split()[1].lower()))
