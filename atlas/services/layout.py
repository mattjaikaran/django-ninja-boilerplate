"""Auto-layout for the atlas city: zones, grid placement, iso projection.

The city is a diagonal isometric band. Zones stack from back to front
(smallest gy to largest gy), tallest first:

- back row: local apps (tallest blocks)
- then the API layer
- then interface externals (web / mobile clients)
- front row: infrastructure slabs (database, cache, brokers)

Ordering zones by descending height keeps short blocks in front of tall
towers, so no tower hides the blocks behind it.

Projection (shared with the renderer):

    x = (gx - gy) * TILE_W
    y = (gx + gy) * TILE_H - h * HEIGHT_SCALE

Painter order sorts nodes by ``gx + gy`` so nothing needs z-index hacks.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

TILE_W = 26.0
TILE_H = 14.3
HEIGHT_SCALE = 16.0


GY_GAP = 3
HEIGHT_FACTOR = 9.0
CHILD_HEIGHT_DIVISOR = 100


def height_for_loc(loc: int) -> int:
    """Map a LOC count to a block height in the 2..12 range."""
    if loc <= 0:
        return 2
    return max(2, min(12, round((loc**0.5) / HEIGHT_FACTOR)))


def height_for_child(loc: int) -> int:
    """Map a component LOC count to a small inside-view block height."""
    if loc <= 0:
        return 2
    return max(2, min(8, loc // CHILD_HEIGHT_DIVISOR))


def iso(gx: float, gy: float, h: int = 0) -> tuple[float, float]:
    """Project grid coordinates to screen space."""
    return (gx - gy) * TILE_W, (gx + gy) * TILE_H - h * HEIGHT_SCALE


def _finalize(nodes: Iterable[dict[str, Any]]) -> None:
    """Assign painter order and screen-space anchor to every node."""
    for node in nodes:
        node["order"] = node["gx"] + node["gy"]
        px, py = iso(node["gx"], node["gy"], node.get("h", 0))
        node["px"], node["py"] = px, py


def assign_layout(
    structures: list[dict[str, Any]], externals: list[dict[str, Any]]
) -> None:
    """Assign grid coordinates, heights, and screen anchors to all nodes."""
    clients = [node for node in externals if node.get("zone") == "client"]
    infra = [node for node in externals if node.get("zone") == "infra"]
    api_nodes = [node for node in structures if node.get("group") == "api"]
    app_nodes = [node for node in structures if node.get("group") == "app"]

    for node in clients:
        node.setdefault("w", 2)
        node.setdefault("h", 1)
        node.setdefault("d", 1)
    for node in infra:
        node.setdefault("w", 2)
        node.setdefault("h", 1)
        node.setdefault("d", 1)
    for node in api_nodes:
        node.setdefault("w", 2)
        node.setdefault("d", 1)
        node["h"] = height_for_loc(node.get("loc", 0))
    for node in app_nodes:
        node.setdefault("w", 1)
        node.setdefault("d", 1)
        node["h"] = height_for_loc(node.get("loc", 0))

    # Zones stack back-to-front (smallest gy first). Tallest first keeps
    # short blocks in front of tall towers instead of hidden behind them.
    zones = [app_nodes, api_nodes, clients, infra]
    zones = [zone for zone in zones if zone]
    zones.sort(
        key=lambda zone: max((n.get("h", 1) for n in zone), default=0),
        reverse=True,
    )

    # Pack each zone in rows of three. Columns step by w + 2 so cubes keep
    # a full gap between them; a wrapped row shifts two tiles right so it
    # never collides with the row above. Zones are GY_GAP rows apart.
    gy = 0
    for zone_nodes in zones:
        gx, col = 0, 0
        for node in zone_nodes:
            node["gx"], node["gy"] = gx, gy
            gx += node["w"] + 2
            col += 1
            if col >= 3:
                gx, col = 2, 0
                gy += 2
        gy += GY_GAP

    _finalize([*structures, *externals])
