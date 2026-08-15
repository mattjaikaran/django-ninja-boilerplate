/* Codebase Atlas — core application logic.
   Loads the atlas data, drives the isometric scene, and wires tooltips,
   zoom/pan, and dot animation. UI overlays (panel, modal, trace, legend)
   live in atlas-ui.js and plug in through AtlasApp.onReady.
   Depends on AtlasScene (atlas-scene.js). No inline styles. */

"use strict";

(() => {
  const app = document.getElementById("atlas-app");
  if (!app) return;

  const state = {
    data: null,
    nodes: new Map(),
    edges: [],
    packetsById: new Map(),
    view: "city",
    insideId: null,
    insideNodes: null,
    zoom: 1,
    panX: 0,
    panY: 0,
    selectedId: null,
    dots: [],
  };

  const readyCallbacks = [];
  const onReady = (fn) => readyCallbacks.push(fn);

  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", "atlas-svg");
  const sceneGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
  svg.appendChild(sceneGroup);
  app.appendChild(svg);

  const tooltip = document.createElement("div");
  tooltip.className = "atlas-tooltip";
  tooltip.style.display = "none";
  tooltip.style.position = "fixed";
  document.body.appendChild(tooltip);

  // ── helpers ────────────────────────────────────────────────────────

  const fmt = (n) => (n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n));

  const groupColor = (groupId) => {
    const group = (state.data.groups || []).find((g) => g.id === groupId);
    return group ? group.color : "#64748b";
  };

  function buildNodes() {
    state.nodes.clear();
    for (const s of state.data.structures || []) {
      state.nodes.set(s.id, { ...s, color: groupColor(s.group), dashed: 0 });
    }
    for (const e of state.data.externals || []) {
      state.nodes.set(e.id, { ...e, color: groupColor(e.group), dashed: 1 });
    }
  }

  function packetsFor(nodeId) {
    const ids = new Set();
    for (const edge of state.data.edges || []) {
      if (edge.f === nodeId || edge.t === nodeId) {
        for (const id of edge.packets || []) ids.add(id);
      }
    }
    return [...ids].map((id) => state.packetsById.get(id)).filter(Boolean);
  }

  // ── rendering ──────────────────────────────────────────────────────

  function applyTransform() {
    sceneGroup.setAttribute(
      "transform",
      `translate(${state.panX} ${state.panY}) scale(${state.zoom})`
    );
  }

  function render() {
    state.dots = [];
    if (state.view === "inside") {
      renderInside();
    } else {
      const { edges } = AtlasScene.renderScene(sceneGroup, state.nodes, state.data.edges);
      state.dots = edges.flatMap((e) => e.dots);
      wireEdgeEvents(edges);
    }
    applyTransform();
  }

  function renderInside() {
    const parent = state.nodes.get(state.insideId);
    const children = (parent && parent.children) || [];
    const nodes = new Map();
    children.forEach((child, i) => {
      const gx = i % 4;
      const gy = Math.floor(i / 4);
      const [px, py] = AtlasScene.iso(gx, gy, child.h);
      nodes.set(`${state.insideId}:${i}`, {
        ...child,
        id: `${state.insideId}:${i}`,
        gx,
        gy,
        w: 1,
        d: 1,
        px,
        py,
        order: gx + gy,
        color: groupColor(parent.group),
      });
    });
    AtlasScene.renderScene(sceneGroup, nodes, []);
    state.insideNodes = nodes;
  }

  function wireEdgeEvents(edges) {
    for (const edge of edges) {
      edge.path.addEventListener("mouseenter", () => {
        edge.path.classList.add("atlas-edge-hot");
      });
      edge.path.addEventListener("mouseleave", () => {
        edge.path.classList.remove("atlas-edge-hot");
      });
      edge.path.addEventListener("click", () => {
        window.AtlasUI && window.AtlasUI.openEdgePackets(edge.path.__edge);
      });
      for (const dot of edge.dots) {
        dot.hit.addEventListener("click", () => {
          window.AtlasUI && window.AtlasUI.openEdgePackets(dot.hit.__edge);
        });
      }
    }
  }

  function wireNodeEvents() {
    const groups = sceneGroup.querySelectorAll(".atlas-node");
    for (const group of groups) {
      const node = group.__node;
      group.addEventListener("mouseenter", () => showTooltip(node));
      group.addEventListener("mouseleave", hideTooltip);
      group.addEventListener("click", () => selectNode(node));
    }
  }

  // ── tooltip ────────────────────────────────────────────────────────

  function showTooltip(node) {
    tooltip.innerHTML = "";
    const b = document.createElement("b");
    b.textContent = node.name;
    tooltip.appendChild(b);
    const line = document.createElement("div");
    line.textContent = `${fmt(node.loc || 0)} LOC · ${node.group}`;
    tooltip.appendChild(line);
    if (node.what) {
      const what = document.createElement("div");
      what.textContent = node.what;
      tooltip.appendChild(what);
    }
    tooltip.style.display = "block";
  }

  function moveTooltip(event) {
    const x = Math.min(event.clientX + 14, window.innerWidth - 340);
    const y = Math.min(event.clientY + 14, window.innerHeight - 140);
    tooltip.style.left = `${x}px`;
    tooltip.style.top = `${y}px`;
  }

  function hideTooltip() {
    tooltip.style.display = "none";
  }

  // ── selection (delegates panels to AtlasUI) ────────────────────────

  function selectNode(node) {
    if (state.view === "inside" && node.id.includes(":")) {
      const parent = state.nodes.get(state.insideId);
      window.AtlasUI.buildPanel(node);
      window.AtlasUI.addBackButton(parent, `${parent.name} — components`);
      return;
    }
    state.selectedId = node.id;
    state.view = "city";
    state.insideId = null;
    render();
    wireNodeEvents();
    window.AtlasUI.buildPanel(node);
    svg.classList.remove("atlas-dragging");
  }

  // ── zoom / pan ─────────────────────────────────────────────────────

  function fit() {
    const rect = app.getBoundingClientRect();
    const nodes = state.view === "inside" && state.insideNodes
      ? state.insideNodes
      : state.nodes;
    const fitResult = AtlasScene.fitTo(
      { width: rect.width, height: rect.height },
      nodes
    );
    state.zoom = fitResult.zoom;
    state.panX = fitResult.panX;
    state.panY = fitResult.panY;
    applyTransform();
  }

  svg.addEventListener("wheel", (event) => {
    event.preventDefault();
    const rect = app.getBoundingClientRect();
    const mx = event.clientX - rect.left;
    const my = event.clientY - rect.top;
    const factor = event.deltaY < 0 ? 1.12 : 0.89;
    const next = Math.max(0.15, Math.min(3, state.zoom * factor));
    const k = next / state.zoom;
    state.panX = mx - (mx - state.panX) * k;
    state.panY = my - (my - state.panY) * k;
    state.zoom = next;
    applyTransform();
  }, { passive: false });

  let dragging = false;
  let lastX = 0;
  let lastY = 0;

  svg.addEventListener("pointerdown", (event) => {
    dragging = true;
    lastX = event.clientX;
    lastY = event.clientY;
    svg.classList.add("atlas-dragging");
    svg.setPointerCapture(event.pointerId);
  });

  svg.addEventListener("pointermove", (event) => {
    if (!dragging) return;
    state.panX += event.clientX - lastX;
    state.panY += event.clientY - lastY;
    lastX = event.clientX;
    lastY = event.clientY;
    applyTransform();
  });

  svg.addEventListener("pointerup", () => {
    dragging = false;
    svg.classList.remove("atlas-dragging");
  });

  app.addEventListener("mousemove", moveTooltip);

  // ── dot animation ─────────────────────────────────────────────────

  function startAnimation() {
    const tick = () => {
      for (const dot of state.dots) {
        dot.t += dot.speed;
        if (dot.t >= 1) dot.t -= 1;
        const p = AtlasScene.pointAt(dot.pts, dot.lens, dot.total, dot.t);
        dot.el.setAttribute("cx", p[0]);
        dot.el.setAttribute("cy", p[1]);
        dot.hit.setAttribute("cx", p[0]);
        dot.hit.setAttribute("cy", p[1]);
      }
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }

  // ── boot ───────────────────────────────────────────────────────────

  async function boot() {
    const dataUrl = app.dataset.url || "/admin/atlas/data.json";
    let data;
    try {
      const response = await fetch(dataUrl);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      data = await response.json();
    } catch (_e) {
      const empty = document.createElement("div");
      empty.className = "atlas-empty";
      empty.textContent = "Failed to load atlas data. Run `python manage.py atlas` and retry.";
      app.appendChild(empty);
      return;
    }
    state.data = data;
    state.packetsById = new Map((data.packets || []).map((p) => [p.id, p]));
    buildNodes();
    render();
    wireNodeEvents();
    startAnimation();
    fit();
    for (const fn of readyCallbacks) fn();
  }

  window.AtlasApp = {
    state,
    app,
    svg,
    sceneGroup,
    render,
    wireNodeEvents,
    selectNode,
    fit,
    applyTransform,
    packetsFor,
    onReady,
  };

  boot();
})();
