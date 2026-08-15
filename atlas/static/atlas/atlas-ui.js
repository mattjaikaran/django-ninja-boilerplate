/* Codebase Atlas — UI overlays.
   Detail panel, packet modal, trace playback, legend, zoom controls,
   and the stats bar. Plugs into the core module through
   window.AtlasApp.onReady. No inline styles. */

"use strict";

(() => {
  const app = document.getElementById("atlas-app");
  if (!app || !window.AtlasApp) return;

  const A = window.AtlasApp;

  const section = (text) => {
    const el = document.createElement("div");
    el.className = "atlas-panel-section-title";
    el.textContent = text;
    return el;
  };

  const p = (text) => {
    const el = document.createElement("p");
    el.textContent = text;
    return el;
  };

  const chip = (text) => {
    const el = document.createElement("span");
    el.className = "atlas-chip";
    el.textContent = text;
    return el;
  };

  // ── detail panel ───────────────────────────────────────────────────

  function buildPanel(node) {
    const existing = app.querySelector(".atlas-panel");
    if (existing) existing.remove();

    const panel = document.createElement("div");
    panel.className = "atlas-panel";

    const head = document.createElement("div");
    head.className = "atlas-panel-head";
    const title = document.createElement("div");
    title.className = "atlas-panel-title";
    title.textContent = node.name;
    const close = document.createElement("button");
    close.className = "atlas-panel-close";
    close.textContent = "×";
    close.addEventListener("click", () => {
      panel.remove();
      A.state.selectedId = null;
      A.render();
      A.wireNodeEvents();
    });
    head.append(title, close);

    const body = document.createElement("div");
    body.className = "atlas-panel-body";

    const meta = document.createElement("p");
    meta.textContent = `${fmt(node.loc || 0)} LOC · ${node.group}`;
    body.appendChild(meta);

    if (node.what) body.append(section("What it does"), p(node.what));
    if (node.how) body.append(section("How it's built"), p(node.how));

    if (node.stats && (node.stats.endpoints > 0 || node.stats.models > 0)) {
      body.append(section("Stats"));
      const chips = document.createElement("div");
      chips.className = "atlas-chips";
      chips.append(chip(`${node.stats.endpoints} endpoints`), chip(`${node.stats.models} models`));
      body.appendChild(chips);
    }

    const packetList = A.packetsFor(node.id);
    if (packetList.length > 0) {
      body.append(section("Data packets"));
      const list = document.createElement("div");
      list.className = "atlas-chip-list";
      for (const packet of packetList) {
        const b = document.createElement("button");
        b.className = "atlas-inline-btn";
        b.textContent = packet.label;
        b.addEventListener("click", () => openPacket(packet));
        list.appendChild(b);
      }
      body.appendChild(list);
    }

    if (node.children && node.children.length > 0) {
      const btn = document.createElement("button");
      btn.className = "atlas-inline-btn";
      btn.textContent = "Zoom into components";
      btn.addEventListener("click", () => {
        A.state.view = "inside";
        A.state.insideId = node.id;
        A.render();
        A.wireNodeEvents();
        addBackButton(node, `${node.name} — components`);
        A.fit();
      });
      body.appendChild(btn);
    }

    panel.append(head, body);
    app.appendChild(panel);
  }

  function addBackButton(parent, titleText) {
    const panel = app.querySelector(".atlas-panel");
    if (!panel) return;
    const head = panel.querySelector(".atlas-panel-head");
    const title = head.querySelector(".atlas-panel-title");
    if (!head.querySelector(".atlas-back")) {
      const back = document.createElement("button");
      back.className = "atlas-inline-btn atlas-back";
      back.textContent = "‹ City map";
      back.addEventListener("click", () => {
        A.selectNode(parent);
      });
      head.insertBefore(back, head.firstChild);
    }
    title.textContent = titleText;
  }

  const fmt = (n) => (n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n));

  // ── packet modal ───────────────────────────────────────────────────

  const modal = document.createElement("div");
  modal.className = "atlas-modal";
  modal.innerHTML =
    '<div class="atlas-modal-card">' +
    '<div class="atlas-modal-head"><div class="atlas-modal-title"></div>' +
    '<div class="atlas-modal-actions"></div></div>' +
    '<div class="atlas-modal-body"><pre class="atlas-json"></pre></div>' +
    "</div>";
  document.body.appendChild(modal);

  const modalTitle = modal.querySelector(".atlas-modal-title");
  const modalJson = modal.querySelector(".atlas-json");
  const modalActions = modal.querySelector(".atlas-modal-actions");

  function openEdgePackets(edge) {
    const packets = (edge.packets || [])
      .map((id) => A.state.packetsById.get(id))
      .filter(Boolean);
    if (packets.length === 0) return;
    openPacket(packets[0], packets);
  }

  function openPacket(packet, siblings) {
    modalTitle.textContent = packet.label;
    modalJson.textContent = JSON.stringify(packet.payload, null, 2);
    modalActions.textContent = "";
    const copy = document.createElement("button");
    copy.className = "atlas-inline-btn";
    copy.textContent = "Copy";
    copy.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(modalJson.textContent);
        copy.textContent = "Copied";
      } catch (_e) {
        copy.textContent = "Copy failed";
      }
    });
    modalActions.appendChild(copy);
    if (siblings && siblings.length > 1) {
      for (const sib of siblings) {
        const b = document.createElement("button");
        b.className = "atlas-inline-btn";
        b.textContent = sib.method ? `${sib.method} ${sib.path}` : sib.label;
        b.addEventListener("click", () => openPacket(sib, siblings));
        modalActions.appendChild(b);
      }
    }
    modal.classList.add("atlas-open");
  }

  modal.addEventListener("click", (event) => {
    if (event.target === modal) modal.classList.remove("atlas-open");
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") modal.classList.remove("atlas-open");
  });

  // ── trace playback ─────────────────────────────────────────────────

  let traceTimer = null;
  let traceIdx = -1;

  function playTrace() {
    const trace = A.state.data.trace || [];
    if (trace.length === 0) return;
    traceIdx = -1;
    traceStep();
    if (traceTimer) clearInterval(traceTimer);
    traceTimer = setInterval(traceStep, 1500);
  }

  function traceStep() {
    const trace = A.state.data.trace || [];
    traceIdx = (traceIdx + 1) % trace.length;
    const [id, caption] = trace[traceIdx];
    const groups = A.sceneGroup.querySelectorAll(".atlas-node");
    groups.forEach((g) => g.classList.add("atlas-dimmed"));
    for (const g of groups) {
      if (g.__node && g.__node.id === id) {
        g.classList.remove("atlas-dimmed");
        g.classList.add("atlas-trace-step");
      }
    }
    updateTraceBar(caption, traceIdx + 1, trace.length);
  }

  function stopTrace() {
    if (traceTimer) {
      clearInterval(traceTimer);
      traceTimer = null;
    }
    A.sceneGroup
      .querySelectorAll(".atlas-node")
      .forEach((g) => g.classList.remove("atlas-dimmed", "atlas-trace-step"));
    const bar = app.querySelector(".atlas-tracebar");
    if (bar) bar.remove();
  }

  function updateTraceBar(caption, step, total) {
    let bar = app.querySelector(".atlas-tracebar");
    if (!bar) {
      bar = document.createElement("div");
      bar.className = "atlas-tracebar";
      const stepEl = document.createElement("span");
      stepEl.className = "atlas-trace-step";
      const cap = document.createElement("span");
      cap.className = "atlas-trace-caption";
      const stop = document.createElement("button");
      stop.className = "atlas-trace-ctrl";
      stop.textContent = "Stop";
      stop.addEventListener("click", stopTrace);
      bar.append(stepEl, cap, stop);
      app.appendChild(bar);
    }
    bar.querySelector(".atlas-trace-step").textContent = `${step}/${total}`;
    bar.querySelector(".atlas-trace-caption").textContent = caption;
  }

  // ── legend, zoom controls, trace button, stats bar ─────────────────

  function buildOverlays() {
    const data = A.state.data;
    const controls = document.createElement("div");
    controls.className = "atlas-controls";

    const legend = document.createElement("div");
    legend.className = "atlas-legend";
    for (const group of data.groups || []) {
      const row = document.createElement("div");
      row.className = "atlas-legend-row";
      const swatch = document.createElement("span");
      swatch.className = "atlas-legend-swatch";
      swatch.style.backgroundColor = group.color;
      const label = document.createElement("span");
      label.textContent = group.name;
      row.append(swatch, label);
      legend.appendChild(row);
    }
    controls.appendChild(legend);

    const zoom = document.createElement("div");
    zoom.className = "atlas-zoom";
    const mk = (label, fn) => {
      const b = document.createElement("button");
      b.className = "atlas-zoom-btn";
      b.textContent = label;
      b.title = label === "+" ? "Zoom in" : label === "−" ? "Zoom out" : "Fit to screen";
      b.addEventListener("click", fn);
      zoom.appendChild(b);
    };
    mk("+", () => {
      A.state.zoom = Math.min(3, A.state.zoom * 1.25);
      A.applyTransform();
    });
    mk("−", () => {
      A.state.zoom = Math.max(0.15, A.state.zoom * 0.8);
      A.applyTransform();
    });
    mk("⤢", A.fit);
    controls.appendChild(zoom);

    const traceBtn = document.createElement("button");
    traceBtn.className = "atlas-inline-btn";
    traceBtn.textContent = "▶ Play request trace";
    traceBtn.addEventListener("click", playTrace);
    controls.appendChild(traceBtn);

    const stats = document.createElement("div");
    stats.className = "atlas-statsbar";
    const items = [
      ["LOC", fmt(data.meta.total_loc)],
      ["apps", data.meta.app_count],
      ["endpoints", data.meta.endpoint_count],
      ["models", data.meta.model_count],
      ["tests", data.meta.test_files],
      ["Django", data.meta.django],
      ["Python", data.meta.python],
    ];
    for (const [label, value] of items) {
      const span = document.createElement("span");
      span.className = "atlas-stat";
      const strong = document.createElement("strong");
      strong.textContent = value;
      const text = document.createElement("span");
      text.textContent = label;
      span.append(strong, text);
      stats.appendChild(span);
    }
    controls.appendChild(stats);

    app.parentElement.appendChild(controls);
  }

  A.onReady(buildOverlays);

  window.AtlasUI = { buildPanel, addBackButton, openEdgePackets };
})();
