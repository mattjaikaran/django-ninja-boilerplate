"""Graph walks over an edge table with a Postgres recursive CTE.

This is the default graph option: it needs no extra service or extension.
Use the `graph` Compose profile (Neo4j) only when you need a graph query
language or algorithms. See docs/AI_LAYER.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.db import NotSupportedError, connection
from django.db.models import Field

if TYPE_CHECKING:
    from django.contrib.auth.base_user import AbstractBaseUser
    from django.contrib.auth.models import AnonymousUser
    from django.db.models import Model


def _column(model: type[Model], name: str) -> str:
    field = model._meta.get_field(name)
    if not isinstance(field, Field):
        raise TypeError(f"{model.__name__}.{name} is not a concrete field.")
    return connection.ops.quote_name(field.column)


def reachable(
    edge_model: type[Model],
    start: Any,
    *,
    user: AbstractBaseUser | AnonymousUser | None,
    source_field: str = "source",
    target_field: str = "target",
    owner_field: str = "owner",
    max_depth: int = 3,
) -> list[tuple[Any, int]]:
    """Return (node id, shortest depth) for each of the caller's nodes reachable
    from ``start``.

    ``edge_model`` has two foreign keys to the same node model, and the node
    model has an ``owner_field`` foreign key to the user. The walk starts only
    if ``user`` owns ``start`` and visits only nodes that ``user`` owns. No
    user, or an anonymous user, returns no nodes. The walk follows edges from
    source to target, stops at ``max_depth`` hops, skips cycles, and leaves
    out ``start``. Rows are ordered by depth, then id.
    """
    if max_depth < 1:
        raise ValueError("max_depth must be at least 1")
    if connection.vendor != "postgresql":
        raise NotSupportedError("reachable() needs PostgreSQL (array paths).")
    if user is None or not user.is_authenticated:
        return []
    table = connection.ops.quote_name(edge_model._meta.db_table)
    source = _column(edge_model, source_field)
    target = _column(edge_model, target_field)
    node_model = edge_model._meta.get_field(target_field).related_model
    if not isinstance(node_model, type):
        raise TypeError(f"{edge_model.__name__}.{target_field} is not a relation.")
    nodes = connection.ops.quote_name(node_model._meta.db_table)
    node_pk = connection.ops.quote_name(node_model._meta.pk.column)
    owner = _column(node_model, owner_field)
    # The ORM cannot express WITH RECURSIVE. nosec B608: identifiers come from
    # model metadata and are quoted; the values are bound parameters.
    sql = f"""
        WITH RECURSIVE walk(node, depth, path) AS (
            SELECT e.{target}, 1, ARRAY[e.{source}, e.{target}]
            FROM {table} e
            JOIN {nodes} s ON s.{node_pk} = e.{source} AND s.{owner} = %s
            JOIN {nodes} t ON t.{node_pk} = e.{target} AND t.{owner} = %s
            WHERE e.{source} = %s
          UNION ALL
            SELECT e.{target}, w.depth + 1, w.path || e.{target}
            FROM {table} e
            JOIN walk w ON e.{source} = w.node
            JOIN {nodes} t ON t.{node_pk} = e.{target} AND t.{owner} = %s
            WHERE w.depth < %s AND e.{target} <> ALL(w.path)
        )
        SELECT node, MIN(depth) AS depth
        FROM walk
        GROUP BY node
        ORDER BY depth, node
    """  # nosec B608
    with connection.cursor() as cursor:
        cursor.execute(sql, [user.pk, user.pk, start, user.pk, max_depth])
        return [(node, depth) for node, depth in cursor.fetchall()]
