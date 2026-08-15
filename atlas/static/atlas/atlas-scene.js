/* Codebase Atlas — isometric scene renderer.
   Pure SVG drawing: iso cubes, edge paths, animated data dots.
   No dependencies. All styles come from atlas.css; no inline styles. */

"use strict";

window.AtlasScene = (() => {
  const TILE_W = 26;
  const TILE_H = 14.3;
  const H_SCALE = 16;
  const SVG_NS = "http://www.w3.org/2000/svg";

  const iso = (gx, gy, h = 0) => [(gx - gy) * TILE_W, (gx + gy) * TILE_H - h * H_SCALE];

  const shade = (hex, amt) => {
    const n = parseInt(hex.slice(1), 16);
    let r = (n >> 16) & 255;
    let g = (n >> 8) & 255;
    let b = n & 255;
    if (amt < 0) {
      r *= 1 + amt;
      g *= 1 + amt;
      b *= 1 + amt;
    } else {
      r += (255 - r) * amt;
      g += (255 - g) * amt;
      b += (255 - b) * amt;
    }
    return `rgb(${r | 0},${g | 0},${b | 0})`;
  };

  const el = (name, attrs, parent) => {
    const node = document.createElementNS(SVG_NS, name);
    for (const [key, value] of Object.entries(attrs || {})) {
      node.setAttribute(key, value);
    }
    if (parent) parent.appendChild(node);
    return node;
  };

  const centerOf = (node) => [
    node.px + ((node.w - node.d) * TILE_W) / 2,
    node.py + ((node.w + node.d) * TILE_H) / 2,
  ];

  function cubeFaces(node) {
    const a = [node.px, node.py];
    const b = [node.px + node.w * TILE_W, node.py + node.w * TILE_H];
    const c = [
      node.px + (node.w - node.d) * TILE_W,
      node.py + (node.w + node.d) * TILE_H,
    ];
    const d = [node.px - node.d * TILE_W, node.py + node.d * TILE_H];
    const drop = node.h * H_SCALE;
    return {
      top: [a, b, c, d],
      right: [a, b, [b[0], b[1] + drop], [a[0], a[1] + drop]],
      left: [a, d, [d[0], d[1] + drop], [a[0], a[1] + drop]],
    };
  }


  const polyPoints = (pts) => pts.map((p) => p.join(",")).join(" ");

  function drawNode(svg, node) {
    const faces = cubeFaces(node);
    const group = el("g", { class: "atlas-node" + (node.dashed ? " atlas-external" : "") }, svg);
    group.__node = node;

    el("polygon", {
      points: polyPoints(faces.top),
      fill: node.color,
      class: "atlas-face-top",
    }, group);
    el("polygon", {
      points: polyPoints(faces.right),
      fill: shade(node.color, -0.35),
      class: "atlas-face-side",
    }, group);
    el("polygon", {
      points: polyPoints(faces.left),
      fill: shade(node.color, -0.2),
      class: "atlas-face-side",
    }, group);

    // Short label as a chip on the left face. Blocks are laid out with
    // gaps, so the face is never covered and the text never meets a
    // neighbour. Long names fall back to the id (title-cased); the
    // tooltip carries the full name.
    const leftCenter = [
      (faces.left[0][0] + faces.left[2][0]) / 2,
      (faces.left[0][1] + faces.left[2][1]) / 2,
    ];
    const display =
      node.name.length <= 12
        ? node.name
        : node.id.charAt(0).toUpperCase() + node.id.slice(1);
    const label = el("text", {
      x: leftCenter[0],
      y: leftCenter[1] + 4,
      class: "atlas-node-label",
      "text-anchor": "middle",
    }, group);
    label.textContent = display;

    // Chip behind the text: the face colors are busy, so a translucent
    // dark pill keeps the label readable without an outline halo.
    const bbox = label.getBBox();
    const padX = 7;
    const padY = 4;
    el("rect", {
      x: bbox.x - padX,
      y: bbox.y - padY,
      width: bbox.width + padX * 2,
      height: bbox.height + padY * 2,
      rx: 6,
      fill: "rgba(15, 23, 42, 0.72)",
      class: "atlas-label-chip",
    }, group);
    group.insertBefore(group.querySelector(".atlas-label-chip"), label);
    return group;
  }

  function pathPoints(edge, nodes) {
    const s = centerOf(nodes.get(edge.f));
    const t = centerOf(nodes.get(edge.t));
    const midY = Math.min(s[1], t[1]) - 28;
    return [s, [s[0], midY], [t[0], midY], t];
  }

  function cumLengths(pts) {
    const lens = [0];
    let total = 0;
    for (let i = 1; i < pts.length; i += 1) {
      total += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
      lens.push(total);
    }
    return { lens, total: total || 1 };
  }

  function pointAt(pts, lens, total, t) {
    const target = t * total;
    for (let i = 1; i < pts.length; i += 1) {
      if (lens[i] >= target) {
        const seg = lens[i] - lens[i - 1] || 1;
        const f = (target - lens[i - 1]) / seg;
        return [
          pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * f,
          pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * f,
        ];
      }
    }
    return pts[pts.length - 1];
  }

  function drawEdge(svg, edge, nodes, labelY) {
    const pts = pathPoints(edge, nodes);
    const { lens, total } = cumLengths(pts);
    const path = el("path", {
      d: `M ${pts[0][0]} ${pts[0][1]} L ${pts[1][0]} ${pts[1][1]} L ${pts[2][0]} ${pts[2][1]} L ${pts[3][0]} ${pts[3][1]}`,
      class: "atlas-edge" + (edge.dashed ? " atlas-edge-dashed" : ""),
    }, svg);
    path.__edge = edge;

    const mid = [(pts[1][0] + pts[2][0]) / 2, labelY];
    el("text", { x: mid[0], y: mid[1], class: "atlas-edge-pay" }, svg).textContent = edge.pay || "";

    const dots = [];
    const count = edge.dashed ? 1 : 2;
    for (let i = 0; i < count; i += 1) {
      const dot = el("circle", { r: 3.2, fill: "#fde68a", class: "atlas-dot" }, svg);
      const hit = el("circle", { r: 10, fill: "transparent", class: "atlas-dot-hit" }, svg);
      hit.__edge = edge;
      dots.push({
        el: dot,
        hit,
        t: i / count,
        speed: edge.dashed ? 0.0012 : 0.0025,
        pts,
        lens,
        total,
      });
    }
    return { path, dots };
  }

  // Edge labels share horizontal segments, so several stack at one y.
  // After drawing, measure the real rendered boxes and nudge colliding
  // labels down until nothing overlaps (labels vs labels, labels vs
  // node chips). Runs in local SVG units, so it is exact.
  function resolveEdgeLabels(svg) {
    const labels = [...svg.querySelectorAll(".atlas-edge-pay")];
    const chips = [...svg.querySelectorAll(".atlas-label-chip")];
    const boxOf = (el) => {
      const b = el.getBBox();
      return { x: b.x, y: b.y, w: b.width, h: b.height };
    };
    const overlaps = (a, b) =>
      a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
    const chipBoxes = chips.map(boxOf);

    labels.forEach((label, i) => {
      const own = boxOf(label);
      for (let guard = 0; guard < 20; guard += 1) {
        const others = labels
          .map((el, k) => (k === i ? null : boxOf(el)))
          .filter(Boolean);
        const hit =
          others.some((o) => overlaps(own, o)) ||
          chipBoxes.some((c) => overlaps(own, c));
        if (!hit) break;
        label.setAttribute("y", parseFloat(label.getAttribute("y")) + 16);
        own.y += 16;
      }
    });
  }


  function renderScene(svg, nodes, edges) {
    svg.textContent = "";
    const sorted = [...nodes.values()].sort((a, b) => a.order - b.order);
    const nodeEls = sorted.map((node) => drawNode(svg, node));

    // Base label position: just above the shared horizontal segment.
    // resolveEdgeLabels() nudges any colliding labels afterward.
    const edgeData = edges.map((edge) => {
      const pts = pathPoints(edge, nodes);
      return drawEdge(svg, edge, nodes, pts[1][1] - 12);
    });
    resolveEdgeLabels(svg);
    return { nodeEls, edges: edgeData };
  }


  function bounds(nodes) {
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    for (const node of nodes.values()) {
      const faces = cubeFaces(node);
      for (const poly of [faces.top, faces.right, faces.left]) {
        for (const p of poly) {
          minX = Math.min(minX, p[0]);
          minY = Math.min(minY, p[1]);
          maxX = Math.max(maxX, p[0]);
          maxY = Math.max(maxY, p[1]);
        }
      }
    }
    return { minX, minY, maxX, maxY };
  }

  function fitTo(viewport, nodes) {
    const b = bounds(nodes);
    // Edge labels render above the top faces and node labels sit on the
    // left faces, outside the cube bounds. Pad the fit so the top text
    // stays inside the viewport and the scene does not fill the canvas.
    const minX = b.minX - 28;
    const minY = b.minY - 56;
    const maxX = b.maxX + 28;
    const maxY = b.maxY + 24;
    const bw = Math.max(maxX - minX, 1);
    const bh = Math.max(maxY - minY, 1);
    const zoom = Math.min(viewport.width / bw, viewport.height / bh) * 0.9;
    return {
      zoom: Math.max(0.15, Math.min(zoom, 1.3)),
      panX: viewport.width / 2 - ((minX + maxX) / 2) * zoom,
      panY: viewport.height / 2 - ((minY + maxY) / 2) * zoom,
    };
  }

  return { iso, shade, el, renderScene, bounds, fitTo, pointAt, cubeFaces };
})();
